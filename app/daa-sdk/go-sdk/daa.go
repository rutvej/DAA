package daa

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"runtime/debug"
	"time"
)

type Client struct {
	BackendURL string
	Token      string
	AppName    string
	httpClient *http.Client
}

type LogPayload struct {
	Content       string `json:"content"`
	AppName       string `json:"app_name"`
	ExceptionType string `json:"exception_type,omitempty"`
}

type LogContent struct {
	Message    string                 `json:"message"`
	StackTrace string                 `json:"stack_trace"`
	Context    map[string]interface{} `json:"context"`
	Timestamp  string                 `json:"timestamp"`
}

func NewClient(backendURL, token, appName string) *Client {
	if backendURL == "" {
		backendURL = os.Getenv("DAA_BACKEND_API_URL")
	}
	if backendURL == "" {
		backendURL = "http://localhost:8000"
	}
	if token == "" {
		token = os.Getenv("DAA_TOKEN")
	}
	if appName == "" {
		appName = os.Getenv("REPO_NAME")
	}
	if appName == "" {
		appName = "default-go-app"
	}

	return &Client{
		BackendURL: backendURL,
		Token:      token,
		AppName:    appName,
		httpClient: &http.Client{Timeout: 10 * time.Second},
	}
}

func (c *Client) CaptureException(err error) error {
	stack := string(debug.Stack())
	content := LogContent{
		Message:    err.Error(),
		StackTrace: stack,
		Context:    make(map[string]interface{}),
		Timestamp:  time.Now().Format(time.RFC3339),
	}

	contentJSON, marshalErr := json.Marshal(content)
	if marshalErr != nil {
		return marshalErr
	}

	payload := LogPayload{
		Content:       string(contentJSON),
		AppName:       c.AppName,
		ExceptionType: fmt.Sprintf("%T", err),
	}

	return c.SendLog(payload)
}

func (c *Client) SendLog(payload LogPayload) error {
	url := fmt.Sprintf("%s/logs/", c.BackendURL)
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return err
	}

	req.Header.Set("Content-Type", "application/json")
	if c.Token != "" {
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.Token))
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("DAA backend returned status code %d", resp.StatusCode)
	}

	return nil
}
