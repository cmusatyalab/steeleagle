package main

import (
	"bytes"
	"fmt"
	"hash/fnv"
	"image"
	"image/color"
	"image/jpeg"
	"math"
	"math/rand"
	"time"

	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	"github.com/rs/zerolog/log"
	"golang.org/x/image/draw"
	"golang.org/x/image/font"
	"golang.org/x/image/font/basicfont"
	"golang.org/x/image/math/fixed"
	"google.golang.org/protobuf/types/known/timestamppb"
)

const (
	// noiseBlock is the side length, in destination pixels, of each noise
	// cell before upscaling. Independent per-pixel noise is far more
	// incompressible than a real photo (which is spatially correlated), so
	// generating noise at a coarser resolution and smoothly upscaling it
	// keeps the texture looking organic while landing JPEG sizes in the
	// same ballpark as real vehicle frames, instead of the few-KB files a
	// flat color background produces.
	noiseBlock = 16
	// noiseAmplitude is the max per-channel +/- jitter applied around the
	// vehicle's base color at each noise cell.
	noiseAmplitude = 30
	// defaultJPEGQuality and the constants above were tuned together (see
	// producers_test.go-style experimentation, not checked in) to land
	// close to ~100KB at 1280x720, matching real vehicle frame sizes.
	defaultJPEGQuality = 90
	// textScale magnifies the 7x13 bitmap font; at native size it is
	// barely legible on a 720p+ frame.
	textScale = 3
)

// vehicleColor derives a deterministic background color from the vehicle
// name, mirroring the GCS squad's mock_imagery_server.py (which uses
// ColorHash) so a given vehicle name reads as the same color across tools.
func vehicleColor(vehicle string) color.RGBA {
	h := fnv.New32a()
	h.Write([]byte(vehicle))
	hue := float64(h.Sum32() % 360)
	r, g, b := hsvToRGB(hue, 0.55, 0.65)
	return color.RGBA{R: r, G: g, B: b, A: 255}
}

func hsvToRGB(h, s, v float64) (uint8, uint8, uint8) {
	c := v * s
	x := c * (1 - math.Abs(math.Mod(h/60, 2)-1))
	m := v - c
	var r, g, b float64
	switch {
	case h < 60:
		r, g, b = c, x, 0
	case h < 120:
		r, g, b = x, c, 0
	case h < 180:
		r, g, b = 0, c, x
	case h < 240:
		r, g, b = 0, x, c
	case h < 300:
		r, g, b = x, 0, c
	default:
		r, g, b = c, 0, x
	}
	return uint8((r + m) * 255), uint8((g + m) * 255), uint8((b + m) * 255)
}

// noiseBackground fills img with a vehicle-colored noise texture, sized so
// its JPEG-compressed weight is representative of a real ~90%-quality
// vehicle frame rather than the few KB a flat color fill produces.
func noiseBackground(img *image.RGBA, vehicle string, seq uint64) {
	bounds := img.Bounds()
	base := vehicleColor(vehicle)

	lw, lh := max(bounds.Dx()/noiseBlock, 1), max(bounds.Dy()/noiseBlock, 1)
	low := image.NewRGBA(image.Rect(0, 0, lw, lh))
	r := rand.New(rand.NewSource(int64(seq)))
	jitter := func(v uint8) uint8 {
		d := r.Intn(2*noiseAmplitude+1) - noiseAmplitude
		n := int(v) + d
		if n < 0 {
			n = 0
		} else if n > 255 {
			n = 255
		}
		return uint8(n)
	}
	for y := 0; y < lh; y++ {
		for x := 0; x < lw; x++ {
			low.SetRGBA(x, y, color.RGBA{R: jitter(base.R), G: jitter(base.G), B: jitter(base.B), A: 255})
		}
	}
	draw.CatmullRom.Scale(img, bounds, low, low.Bounds(), draw.Src, nil)
}

// drawScaledText renders label at textScale magnification by drawing it at
// native size onto a small buffer and nearest-neighbor upscaling that into
// img, keeping the bitmap font crisp instead of blurring it. x, y is the
// baseline of the final (scaled) text, matching basicfont's usual
// Dot-is-baseline convention.
func drawScaledText(img *image.RGBA, x, y int, label string, c color.Color) {
	face := basicfont.Face7x13
	widthPx := font.MeasureString(face, label).Ceil()
	metrics := face.Metrics()
	heightPx := metrics.Height.Ceil()
	ascentPx := metrics.Ascent.Ceil()
	if widthPx <= 0 || heightPx <= 0 {
		return
	}

	small := image.NewRGBA(image.Rect(0, 0, widthPx, heightPx))
	d := &font.Drawer{
		Dst:  small,
		Src:  image.NewUniform(c),
		Face: face,
		Dot:  fixed.P(0, ascentPx),
	}
	d.DrawString(label)

	dst := image.Rect(x, y-ascentPx*textScale, x+widthPx*textScale, y-ascentPx*textScale+heightPx*textScale)
	draw.NearestNeighbor.Scale(img, dst, small, small.Bounds(), draw.Over, nil)
}

func drawDot(img *image.RGBA, cx, cy, radius int, c color.Color) {
	bounds := img.Bounds()
	for dy := -radius; dy <= radius; dy++ {
		for dx := -radius; dx <= radius; dx++ {
			if dx*dx+dy*dy > radius*radius {
				continue
			}
			x, y := cx+dx, cy+dy
			if x >= bounds.Min.X && x < bounds.Max.X && y >= bounds.Min.Y && y < bounds.Max.Y {
				img.Set(x, y, c)
			}
		}
	}
}

// syntheticJPEG renders a frame carrying the vehicle name, a timestamp and
// frame counter, and a dot that bounces left-to-right so motion is visible
// between frames -- the same layout as the GCS squad's
// mock_imagery_server.py, so frames from this tool look familiar next to
// that one.
func syntheticJPEG(vehicle string, seq uint64, width, height, quality int) []byte {
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	noiseBackground(img, vehicle, seq)

	white := color.RGBA{R: 255, G: 255, B: 255, A: 255}
	lineHeight := basicfont.Face7x13.Metrics().Height.Ceil() * textScale
	firstBaseline := height/2 - lineHeight
	drawScaledText(img, 20, firstBaseline, vehicle, white)
	drawScaledText(img, 20, firstBaseline+lineHeight+8, fmt.Sprintf("frame %d  %s", seq, time.Now().Format("15:04:05")), white)

	// Bounces left-to-right so motion is visible even between same-second frames.
	span := width - 40
	pos := int(seq) * 7 % (span * 2)
	x := pos
	if pos > span {
		x = span*2 - pos
	}
	drawDot(img, x+20, height-40, 15, white)

	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, img, &jpeg.Options{Quality: quality}); err != nil {
		log.Err(err).Msg("failed to encode synthetic frame as JPEG")
		return nil
	}
	return buf.Bytes()
}

// syntheticFrame builds an EncodedFrame wrapping a synthetic JPEG for tick
// seq, sharing the same synthetic position as the telemetry producer so
// stored imagery lines up with reported vehicle position.
func syntheticFrame(vehicle string, seq uint64, width, height, quality int) *telemetrypb.EncodedFrame {
	return telemetrypb.EncodedFrame_builder{
		Timestamp:   timestamppb.Now(),
		EncodedData: syntheticJPEG(vehicle, seq, width, height, quality),
		Id:          seq,
	}.Build()
}
