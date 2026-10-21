package daemon

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"errors"
	"fmt"
	"io/fs"
	"math/big"
	"os"
	"path/filepath"
	"time"

	"github.com/cmusatyalab/steeleagle/v4/core/util"
)

// lcsCert returns the PEM encoded cert for the local compute service, which
// remote daemons use to verify it. The cert and its key are kept in the data
// directory; if there is no valid cert there, a new self-signed one is
// generated and saved. Only the cert is returned, never the key.
func (d *Daemon) lcsCert() (string, error) {
	d.certMu.Lock()
	defer d.certMu.Unlock()
	dir, err := util.GetDataDir()
	if err != nil {
		return "", err
	}
	certPath := filepath.Join(dir, LcsCertFileName)
	keyPath := filepath.Join(dir, LcsKeyFileName)
	if cert, err := readCert(certPath, keyPath); err == nil {
		return cert, nil
	} else if !errors.Is(err, fs.ErrNotExist) {
		d.log.Warn().Err(err).Str("path", certPath).Msg("replacing invalid local compute cert")
	}

	cert, key, err := generateCert(d.Config.Daemon.Hostname)
	if err != nil {
		return "", err
	}
	// The key is written first, so a cert on disk always has its key
	if err := os.WriteFile(keyPath, key, 0600); err != nil {
		return "", err
	}
	if err := os.WriteFile(certPath, cert, 0644); err != nil {
		return "", err
	}
	d.log.Info().Str("path", certPath).Msg("generated local compute cert")
	return string(cert), nil
}

// readCert reads the PEM cert at certPath, checking that its key exists and
// that it hasn't expired.
func readCert(certPath, keyPath string) (string, error) {
	if _, err := os.Stat(keyPath); err != nil {
		return "", err
	}
	content, err := os.ReadFile(certPath)
	if err != nil {
		return "", err
	}
	block, _ := pem.Decode(content)
	if block == nil || block.Type != "CERTIFICATE" {
		return "", fmt.Errorf("no PEM cert in %s", certPath)
	}
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return "", err
	}
	if time.Now().After(cert.NotAfter) {
		return "", fmt.Errorf("cert in %s expired at %s", certPath, cert.NotAfter)
	}
	return string(content), nil
}

// generateCert creates a self-signed ECDSA cert for hostname, returning the PEM
// encoded cert and key.
func generateCert(hostname string) ([]byte, []byte, error) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return nil, nil, err
	}
	serial, err := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 128))
	if err != nil {
		return nil, nil, err
	}
	now := time.Now()
	template := &x509.Certificate{
		SerialNumber:          serial,
		Subject:               pkix.Name{CommonName: hostname},
		DNSNames:              []string{hostname},
		NotBefore:             now.Add(-time.Hour), // tolerate clock skew
		NotAfter:              now.Add(lcsCertValidity),
		KeyUsage:              x509.KeyUsageDigitalSignature | x509.KeyUsageCertSign,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		BasicConstraintsValid: true,
		IsCA:                  true,
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		return nil, nil, err
	}
	keyDer, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		return nil, nil, err
	}
	return pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der}),
		pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: keyDer}), nil
}
