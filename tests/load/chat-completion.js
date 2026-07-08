import http from 'k6/http';
import { check, fail, sleep } from 'k6';
import { Trend, Counter, Rate } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import { scenario, vu } from 'k6/execution';

const BASE_URL = __ENV.BASE_URL || 'https://staging.chat.beyondtheloop.ai';
const MODEL_ID = __ENV.MODEL_ID || fail('MODEL_ID env var required (DB id of a Model row, not the friendly name)');
const THINK_TIME = Number(__ENV.THINK_TIME || 2);
const STREAM = (__ENV.STREAM || 'true') === 'false';
// How many small-body samples to log per VU. Keeps output readable while
// still surfacing whether "successful" responses are real content or the
// server's short SSE error frame.
const BODY_LOG_MAX_PER_VU = Number(__ENV.BODY_LOG_MAX_PER_VU || 3);
// Below this size, a "successful" response is suspicious — real streamed
// completions are hundreds of bytes minimum. Non-stream JSON responses too.
const SUSPICIOUS_BODY_BYTES = Number(__ENV.SUSPICIOUS_BODY_BYTES || 300);

const users = new SharedArray('users', () => {
  const raw = __ENV.USERS_JSON;
  if (!raw) fail('USERS_JSON env var required (JSON array of {email,password})');
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed) || parsed.length === 0) fail('USERS_JSON must be a non-empty array');
  return parsed;
});

const prompts = new SharedArray('prompts', () => [
  'Summarize the concept of eventual consistency in one paragraph.',
  'Write a haiku about Kubernetes autoscaling.',
  'What are three tradeoffs of running PostgreSQL on Cloud SQL vs. self-managed?',
  'Explain OAuth2 authorization code flow in 4 bullet points.',
  'Give me a one-line description of the CAP theorem.'
]);

const ttft = new Trend('chat_ttft_ms', true);
const totalDuration = new Trend('chat_total_ms', true);
const streamBytes = new Trend('chat_stream_bytes');
const chatErrors = new Counter('chat_errors');
const chatOk = new Rate('chat_success_rate');
// Real-content rate: HTTP 200 alone is not enough — the server can
// return 200 + a tiny SSE error frame when downstream (LiteLLM/DB) fails
// mid-stream, since headers were already committed. Track separately.
const realContentRate = new Rate('chat_real_content_rate');

// Per-VU counter of how many small-body samples we've already logged.
// k6 exposes per-VU state via a globalthis object per VU sandbox.
let bodySamplesLogged = 0;

export const options = {
  scenarios: {
    ramp: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 5 },
        { duration: '2m', target: 20 },
        { duration: '3m', target: 50 },
        { duration: '2m', target: 100 },
        { duration: '1m', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    chat_ttft_ms: ['p(95)<4000', 'p(99)<8000'],
    chat_total_ms: ['p(95)<30000'],
    chat_success_rate: ['rate>0.98'],
    // Independent from success_rate: 200-status-only is not enough.
    chat_real_content_rate: ['rate>0.95'],
    http_req_failed: ['rate<0.02'],
  },
  discardResponseBodies: false,
  noConnectionReuse: false,
};

export function setup() {
  const tokens = users.map((u) => {
    const res = http.post(
      `${BASE_URL}/api/v1/auths/signin`,
      JSON.stringify({ email: u.email, password: u.password }),
      { headers: { 'Content-Type': 'application/json' }, tags: { name: 'signin' } }
    );
    if (res.status !== 200) {
      fail(`signin failed for ${u.email}: ${res.status} ${res.body}`);
    }
    const body = res.json();
    return { email: u.email, token: body.token };
  });
  console.log(`signed in ${tokens.length} users`);
  return { tokens };
}

export default function (data) {
  const cred = data.tokens[scenario.iterationInTest % data.tokens.length];
  const prompt = prompts[Math.floor(Math.random() * prompts.length)];
  const chatId = crypto.randomUUID();
  const messageId = crypto.randomUUID();

  const payload = {
    model: MODEL_ID,
    stream: STREAM,
    chat_id: chatId,
    id: messageId,
    session_id: chatId,
    messages: [{ role: 'user', content: prompt }],
  };

  const t0 = Date.now();
  const res = http.post(`${BASE_URL}/api/chat/completions`, JSON.stringify(payload), {
    headers: {
      'Authorization': `Bearer ${cred.token}`,
      'Content-Type': 'application/json',
      'Accept': STREAM ? 'text/event-stream' : 'application/json',
    },
    tags: { name: 'chat_completion' },
    timeout: '60s',
  });
  const t1 = Date.now();

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'body non-empty': (r) => r.body && r.body.length > 0,
  });

  chatOk.add(ok);
  if (!ok) {
    chatErrors.add(1);
    console.error(`chat failed ${res.status} for ${cred.email}: ${String(res.body).slice(0, 200)}`);
  } else {
    ttft.add(res.timings.waiting);
    totalDuration.add(t1 - t0);
    streamBytes.add(res.body.length);

    // A real chat response has either "role":"assistant" (non-stream JSON)
    // or a substantial body of streamed SSE frames. If neither holds, the
    // server likely returned a single-frame error payload with status 200.
    const body = String(res.body);
    const looksReal = body.length >= SUSPICIOUS_BODY_BYTES
      || body.includes('"role":"assistant"')
      || body.includes('"delta":{"content"');
    realContentRate.add(looksReal);

    if (!looksReal && bodySamplesLogged < BODY_LOG_MAX_PER_VU) {
      bodySamplesLogged += 1;
      console.warn(
        `VU${vu.idInTest} suspicious 200 (${body.length}B, waited ${Math.round(res.timings.waiting)}ms): ` +
        body.slice(0, 250).replace(/\n/g, '\\n')
      );
    }
  }

  sleep(THINK_TIME);
}
