// Command server serves the combined sound-tools page from a scratch container.
package main

import (
	"bytes"
	"compress/gzip"
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"
)

var compressible = map[string]bool{
	".html": true, ".js": true, ".css": true, ".json": true, ".svg": true, ".txt": true,
}

type gzEntry struct {
	mod  time.Time
	size int64
	data []byte
}

type fileServer struct {
	root string
	mu   sync.Mutex
	gz   map[string]gzEntry
}

func (s *fileServer) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", "GET, HEAD")
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if r.URL.Path == "/healthz" {
		fmt.Fprintln(w, "ok")
		return
	}

	name := path.Clean("/" + r.URL.Path)
	for _, part := range strings.Split(name, "/") {
		if strings.HasPrefix(part, ".") {
			http.NotFound(w, r)
			return
		}
	}
	full := filepath.Join(s.root, filepath.FromSlash(name))
	info, err := os.Stat(full)
	if err == nil && info.IsDir() {
		full = filepath.Join(full, "index.html")
		info, err = os.Stat(full)
	}
	if err != nil || info.IsDir() {
		http.NotFound(w, r)
		return
	}

	h := w.Header()
	h.Set("Cache-Control", "no-cache")
	h.Set("X-Content-Type-Options", "nosniff")
	etag := fmt.Sprintf(`"%x-%x`, info.ModTime().UnixNano(), info.Size())

	ext := strings.ToLower(filepath.Ext(full))
	if compressible[ext] && strings.Contains(r.Header.Get("Accept-Encoding"), "gzip") {
		data, err := s.gzipped(full, info)
		if err == nil {
			h.Set("Content-Encoding", "gzip")
			h.Set("Vary", "Accept-Encoding")
			h.Set("ETag", etag+`-gz"`)
			http.ServeContent(w, r, full, info.ModTime(), bytes.NewReader(data))
			return
		}
		log.Printf("gzip %s: %v", full, err)
	}

	f, err := os.Open(full)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	defer f.Close()
	h.Set("ETag", etag+`"`)
	http.ServeContent(w, r, full, info.ModTime(), f)
}

func (s *fileServer) gzipped(full string, info os.FileInfo) ([]byte, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if e, ok := s.gz[full]; ok && e.mod.Equal(info.ModTime()) && e.size == info.Size() {
		return e.data, nil
	}
	raw, err := os.ReadFile(full)
	if err != nil {
		return nil, err
	}
	var buf bytes.Buffer
	zw, _ := gzip.NewWriterLevel(&buf, gzip.BestCompression)
	if _, err := zw.Write(raw); err != nil {
		return nil, err
	}
	if err := zw.Close(); err != nil {
		return nil, err
	}
	s.gz[full] = gzEntry{mod: info.ModTime(), size: info.Size(), data: buf.Bytes()}
	return buf.Bytes(), nil
}

func healthcheck(port string) int {
	client := http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get("http://127.0.0.1:" + port + "/healthz")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return 1
	}
	return 0
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func main() {
	port := envOr("PORT", "8080")
	if len(os.Args) > 1 && os.Args[1] == "healthcheck" {
		os.Exit(healthcheck(port))
	}
	root := envOr("ROOT", "/srv")

	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           &fileServer{root: root, gz: map[string]gzEntry{}},
		ReadHeaderTimeout: 10 * time.Second,
	}

	// The binary runs as PID 1, so SIGTERM from `docker stop` must be handled here.
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		srv.Shutdown(shutdownCtx)
	}()

	log.Printf("serving %s on :%s", root, port)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
}
