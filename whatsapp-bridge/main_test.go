package main

import "testing"

func TestExtractDirectPathFromURLKeepsSignature(t *testing.T) {
	// whatsmeow downloads via the direct path only and appends "&hash=...",
	// so the path must keep the signed query (oh/oe) the CDN checks.
	url := "https://mmg.whatsapp.net/o1/v/t24/f2/m231/AQOzvMnJj5in?ccb=9-4&oh=01_Q5Aa2A&oe=6900AB12&_nc_sid=e6ed6c&mms3=true"
	want := "/o1/v/t24/f2/m231/AQOzvMnJj5in?ccb=9-4&oh=01_Q5Aa2A&oe=6900AB12&_nc_sid=e6ed6c"

	if got := extractDirectPathFromURL(url); got != want {
		t.Errorf("extractDirectPathFromURL()\n got: %s\nwant: %s", got, want)
	}
}
