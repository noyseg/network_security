/* tracker.js — browser-side event pings for the simulation.
 *
 * Reads campaign_id, subject_code, variant from <body data-*> attributes.
 * If any are missing (e.g., preview mode), every method becomes a no-op
 * so the script is safe to include on any page.
 *
 * STRICT no-leak rule: this file must never read input.value or input.name,
 * and must never iterate form fields by name. Only the input *count* is
 * ever sent in any request body.
 */
(function (window, document) {
    'use strict';

    var ds = document.body.dataset || {};
    var campaignId = parseInt(ds.campaignId || '', 10);
    var subjectCode = ds.subjectCode || '';
    var variant = ds.variant || '';

    var pageLoadTime = Date.now();
    var hasStartedInteraction = false;
    var hasPingedExit = false;

    function hasIdentifiers() {
        return !isNaN(campaignId) && campaignId > 0 && subjectCode && variant;
    }

    function postPing(payload) {
        var body = JSON.stringify(payload);
        if (window.navigator && navigator.sendBeacon) {
            try {
                var blob = new Blob([body], { type: 'application/json' });
                if (navigator.sendBeacon('/events/ping', blob)) {
                    return;
                }
            } catch (e) {
                // fall through to fetch
            }
        }
        try {
            fetch('/events/ping', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: body,
                keepalive: true
            }).catch(function () { /* best-effort */ });
        } catch (e) { /* best-effort */ }
    }

    function recordInteractionStart() {
        if (hasStartedInteraction || !hasIdentifiers()) return;
        hasStartedInteraction = true;
        postPing({
            event_type: 'form_interaction_started',
            campaign_id: campaignId,
            subject_code: subjectCode,
            variant: variant
        });
    }

    function recordExit() {
        if (hasPingedExit || !hasIdentifiers()) return;
        hasPingedExit = true;
        postPing({
            event_type: 'landing_exited',
            campaign_id: campaignId,
            subject_code: subjectCode,
            variant: variant,
            metadata: { time_on_page_ms: Date.now() - pageLoadTime }
        });
    }

    function recordFakeSubmit(form) {
        if (!hasIdentifiers()) return;
        var fieldCount = form.querySelectorAll('input').length;
        fetch('/landing/' + campaignId + '/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                subject_code: subjectCode,
                variant: variant,
                field_count: fieldCount
            })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data && data.redirect) {
                window.location = data.redirect;
            }
        })
        .catch(function () { /* best-effort */ });
    }

    function start() {
        if (!hasIdentifiers()) return;

        document.addEventListener('focusin', function (evt) {
            if (evt.target && evt.target.tagName === 'INPUT') {
                recordInteractionStart();
            }
        });

        window.addEventListener('beforeunload', recordExit);
        window.addEventListener('pagehide', recordExit);

        var form = document.getElementById('fake-login-form');
        if (form) {
            form.addEventListener('submit', function (evt) {
                evt.preventDefault();
                recordFakeSubmit(form);
            });
        }
    }

    window.tracker = {
        start: start,
        recordInteractionStart: recordInteractionStart,
        recordFakeSubmit: recordFakeSubmit,
        recordExit: recordExit
    };
}(window, document));
