package daemon

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"
	"math/big"
	"os"
	"path/filepath"
	"time"

	"github.com/cmusatyalab/steeleagle/v4/core/util"
)

// getCert gets the PEM encoded cert from the creds/ directory, which remote daemons
// use to verify the local compute server.
func (d *Daemon) getCert() (string, error) {
	path, err := util.GetCredsDir()
	if err != nil {
		d.log.Error().Err(err).Str("path", path).Msg("failed to read creds directory")
		return "", err
	}
	certPath := filepath.Join(path, LcsCertFileName)
	keyPath := filepath.Join(path, LcsKeyFileName)
	// If a valid cert is found, return it
	if cert, err := readCert(certPath, keyPath); err == nil {
		return string(pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: cert})), nil
	}

	// Generate new keys, then return the cert
	d.log.Info().Str("path", certPath).Msg("replacing invalid or missing certificate")
	cert, key, err := generateCert(LcsServerName)
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
	return string(pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: cert})), nil
}

// readCert reads the DER cert at certPath, checking that its key exists, that
// it hasn't expired and that it is for the local compute server name.
func readCert(certPath, keyPath string) ([]byte, error) {
	if _, err := os.Stat(keyPath); err != nil {
		return nil, err
	}
	der, err := os.ReadFile(certPath)
	if err != nil {
		return nil, err
	}
	cert, err := x509.ParseCertificate(der)
	if err != nil {
		return nil, fmt.Errorf("no DER cert in %s: %w", certPath, err)
	}
	if time.Now().After(cert.NotAfter) {
		return nil, fmt.Errorf("cert in %s expired at %s", certPath, cert.NotAfter)
	}
	// A cert made for another name, e.g. by an older version, is refused by clients
	if err := cert.VerifyHostname(LcsServerName); err != nil {
		return nil, fmt.Errorf("cert in %s is not for %s: %w", certPath, LcsServerName, err)
	}
	return der, nil
}

// generateCert creates a self-signed ECDSA cert for name, the name Uriel clients
// connect with, returning the DER encoded cert and PKCS #8 key.
func generateCert(name string) ([]byte, []byte, error) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return nil, nil, err
	}
	serial, err := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 128))
	if err != nil {
		return nil, nil, err
	}
	now := time.Now()
	// Uriel clients trust the cert itself, so it must not be a CA cert
	template := &x509.Certificate{
		SerialNumber:          serial,
		Subject:               pkix.Name{CommonName: name},
		DNSNames:              []string{name},
		NotBefore:             now.Add(-time.Hour), // tolerate clock skew
		NotAfter:              now.Add(LcsCertValidity),
		KeyUsage:              x509.KeyUsageDigitalSignature,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		BasicConstraintsValid: true,
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		return nil, nil, err
	}
	keyDer, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		return nil, nil, err
	}
	return der, keyDer, nil
}
