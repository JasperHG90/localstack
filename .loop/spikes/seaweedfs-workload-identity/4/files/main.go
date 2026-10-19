// Gets credentials and writes one object to $BUCKET. With CREDS_JSON (the
// credential_process output of the loki helper) it uses those static creds;
// otherwise it uses minio-go v7.1.0 credentials.IAM as tempo 2.10.8 does
// (Endpoint=TEST_IAM_ENDPOINT, AWS_WEB_IDENTITY_TOKEN_FILE, AWS_ROLE_ARN).
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

func main() {
	var creds *credentials.Credentials
	if p := os.Getenv("CREDS_JSON"); p != "" {
		var c struct{ AccessKeyId, SecretAccessKey, SessionToken string }
		b, _ := os.ReadFile(p)
		if err := json.Unmarshal(b, &c); err != nil || c.AccessKeyId == "" {
			fmt.Println("CREDS FAIL: bad helper output:", err)
			os.Exit(1)
		}
		creds = credentials.NewStaticV4(c.AccessKeyId, c.SecretAccessKey, c.SessionToken)
	} else {
		iam := func() *credentials.IAM {
			return &credentials.IAM{Client: &http.Client{Transport: http.DefaultTransport}, Endpoint: os.Getenv("TEST_IAM_ENDPOINT")}
		}
		creds = credentials.NewChainCredentials([]credentials.Provider{iam()})
		v, err := creds.GetWithContext(&credentials.CredContext{Client: http.DefaultClient})
		if err != nil || v.AccessKeyID == "" {
			_, perr := iam().RetrieveWithCredContext(&credentials.CredContext{Client: http.DefaultClient})
			fmt.Println("STS FAIL: chain gave anonymous creds; provider error:", perr)
			os.Exit(1)
		}
		fmt.Println("STS OK: access key", v.AccessKeyID[:6]+"...")
	}
	c, err := minio.New(os.Getenv("S3_ENDPOINT"), &minio.Options{Creds: creds, Region: "us-east-1"})
	if err != nil {
		fmt.Println("CLIENT FAIL:", err)
		os.Exit(1)
	}
	b := os.Getenv("BUCKET")
	_, err = c.PutObject(context.Background(), b, "spike.txt", strings.NewReader("hi"), 2, minio.PutObjectOptions{})
	if err != nil {
		fmt.Println("PUT", b, "FAIL:", err)
		os.Exit(1)
	}
	fmt.Println("PUT", b, "OK")
}
