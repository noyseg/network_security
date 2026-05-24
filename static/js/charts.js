/* charts.js — dashboard rendering.
 *
 * Reads the campaign ID from <body data-campaign-id="...">, fetches the
 * aggregated JSON from /admin/dashboard/<id>/data, and renders:
 *
 *   1. A bar chart of the funnel  (opens -> clicks -> visits -> submits)
 *   2. A grouped bar of variants A vs B on click rate + submit rate
 *   3. The eight summary tiles at the top of the page
 *
 * No state, no globals beyond the chart instances. Re-runs on
 * DOMContentLoaded only.
 */

(function () {
    'use strict';

    function fmtMs(ms) {
        if (!ms || ms < 1) return '0 ms';
        if (ms < 1000) return ms + ' ms';
        return (ms / 1000).toFixed(1) + ' s';
    }

    function fmtPct(rate) {
        if (rate == null) return '0%';
        return (rate * 100).toFixed(1) + '%';
    }

    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function fillTiles(totals) {
        setText('tile-opens',        totals.opens);
        setText('tile-clicks',       totals.clicks);
        setText('tile-visits',       totals.visits);
        setText('tile-submits',      totals.submits);
        setText('tile-click-rate',   fmtPct(totals.click_rate));
        setText('tile-submit-rate',  fmtPct(totals.submit_rate));
        setText('tile-avg-response', fmtMs(totals.avg_response_time_ms));
        setText('tile-avg-page',     fmtMs(totals.avg_time_on_page_ms));
    }

    function renderFunnel(canvasId, totals) {
        var ctx = document.getElementById(canvasId);
        if (!ctx || typeof Chart === 'undefined') return;
        return new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Opens', 'Clicks', 'Visits', 'Submits'],
                datasets: [{
                    label: 'Distinct subjects',
                    data: [totals.opens, totals.clicks, totals.visits, totals.submits],
                    backgroundColor: ['#2563eb', '#4f46e5', '#7c3aed', '#dc2626']
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
            }
        });
    }

    function renderVariants(canvasId, variants) {
        var ctx = document.getElementById(canvasId);
        if (!ctx || typeof Chart === 'undefined') return;
        var a = variants.A || {}; var b = variants.B || {};
        return new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Click rate', 'Submit rate'],
                datasets: [
                    {
                        label: 'A',
                        data: [(a.click_rate || 0) * 100, (a.submit_rate || 0) * 100],
                        backgroundColor: '#2563eb'
                    },
                    {
                        label: 'B',
                        data: [(b.click_rate || 0) * 100, (b.submit_rate || 0) * 100],
                        backgroundColor: '#dc2626'
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: function (v) { return v + '%'; } }
                    }
                }
            }
        });
    }

    function isEmpty(totals) {
        return !totals.opens && !totals.clicks && !totals.visits && !totals.submits;
    }

    document.addEventListener('DOMContentLoaded', function () {
        var campaignId = document.body.getAttribute('data-campaign-id');
        if (!campaignId) {
            console.warn('charts.js: no data-campaign-id on <body>');
            return;
        }
        fetch('/admin/dashboard/' + campaignId + '/data', {
            credentials: 'same-origin'
        })
            .then(function (r) { return r.json(); })
            .then(function (payload) {
                if (payload.error) {
                    console.error('dashboard data error:', payload.error);
                    return;
                }
                fillTiles(payload.totals);
                renderFunnel('chart-funnel', payload.totals);
                renderVariants('chart-variants', payload.variants);
                if (isEmpty(payload.totals)) {
                    var empty = document.getElementById('empty-state');
                    if (empty) empty.style.display = 'block';
                }
            })
            .catch(function (err) {
                console.error('dashboard fetch failed:', err);
            });
    });
})();
