// Gets credentials the way tempo 2.10.8 does (credentials.IAM with
// Endpoint=TEST_IAM_ENDPOINT, token from AWS_WEB_IDENTITY_TOKEN_FILE), then
// writes one object to the tempo bucket.
package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"strings"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

func main() {
	iam := func() *credentials.IAM {
		return &credentials.IAM{
			Client:   &http.Client{Transport: http.DefaultTransport},
			Endpoint: os.Getenv("TEST_IAM_ENDPOINT"),
		}
	}
	creds := credentials.NewChainCredentials([]credentials.Provider{iam()})
	v, err := creds.GetWithContext(&credentials.CredContext{Client: http.DefaultClient})
	if err != nil || v.AccessKeyID == "" {
		// The chain swallows provider errors and returns empty (anonymous)
		// creds, so ask the provider directly for the reason.
		_, perr := iam().RetrieveWithCredContext(&credentials.CredContext{Client: http.DefaultClient})
		fmt.Println("STS FAIL: chain gave anonymous creds; provider error:", perr)
		os.Exit(1)
	}
	fmt.Println("STS OK: access key", v.AccessKeyID[:6]+"...")
	c, err := minio.New(os.Getenv("S3_ENDPOINT"), &minio.Options{Creds: creds, Region: "us-east-1"})
	if err != nil {
		fmt.Println("CLIENT FAIL:", err)
		os.Exit(1)
	}
	ctx := context.Background()
	if err := c.MakeBucket(ctx, "tempo", minio.MakeBucketOptions{}); err != nil {
		fmt.Println("MakeBucket:", err)
	}
	_, err = c.PutObject(ctx, "tempo", "spike.txt", strings.NewReader("hi"), 2, minio.PutObjectOptions{})
	if err != nil {
		fmt.Println("PUT FAIL:", err)
		os.Exit(1)
	}
	fmt.Println("PUT OK")
}
