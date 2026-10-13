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

func TestBackfillWaitersMatchByJID(t *testing.T) {
	r := &backfillWaiterRegistry{waiters: make(map[string]chan struct{})}
	a, _ := r.register("a@s.whatsapp.net")
	b, _ := r.register("b@lid")

	r.notify([]string{"b@lid"})

	select {
	case <-b:
	default:
		t.Fatal("matching waiter was not woken")
	}
	select {
	case <-a:
		t.Fatal("non-matching waiter was woken")
	default:
	}
}

func TestBackfillWaitersFallbackToSingleWaiter(t *testing.T) {
	// The phone may answer a LID request with the phone-number JID.
	r := &backfillWaiterRegistry{waiters: make(map[string]chan struct{})}
	ch, _ := r.register("123@lid")

	r.notify([]string{"15550001111@s.whatsapp.net"})

	select {
	case <-ch:
	default:
		t.Fatal("single pending waiter was not woken by unmatched JID")
	}
}

func TestBackfillWaitersRejectDuplicate(t *testing.T) {
	r := &backfillWaiterRegistry{waiters: make(map[string]chan struct{})}
	if _, ok := r.register("a@s.whatsapp.net"); !ok {
		t.Fatal("first register failed")
	}
	if _, ok := r.register("a@s.whatsapp.net"); ok {
		t.Fatal("duplicate register should fail")
	}
	r.unregister("a@s.whatsapp.net")
	if _, ok := r.register("a@s.whatsapp.net"); !ok {
		t.Fatal("register after unregister failed")
	}
}
