const vm = require('vm'), fs = require('fs');
const base = `http://127.0.0.1:${process.env.PORT}`, TOKEN = process.env.TOKEN;
const results = []; const check = (n, ok, extra) => { results.push([n, !!ok, extra || '']); };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

function makeWindow(hash, promptAnswers) {
  const store = {}; const calls = { prompt: 0, replaceState: 0 };
  const sb = {
    console, Headers, TextDecoder, AbortController, setTimeout, Promise, Object, URL,
    fetch: (u, o) => fetch(new URL(u, base), o),
    sessionStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
  };
  sb.window = sb;
  sb.location = { hash, pathname: '/', search: '' };
  sb.history = { replaceState: () => { calls.replaceState++; sb.location.hash = ''; } };
  sb.prompt = () => { calls.prompt++; return promptAnswers.length ? promptAnswers.shift() : null; };
  vm.createContext(sb);
  vm.runInContext(fs.readFileSync(process.env.AUTH_JS, 'utf8'), sb);
  return { sb, store, calls };
}

(async () => {
  // A + B: token adopted from the fragment, stripped from the address bar, then used
  let w = makeWindow('#token=' + encodeURIComponent(TOKEN), []);
  check('A fragment adopted into sessionStorage', w.store.ocbrain_api_token === TOKEN);
  check('A fragment removed from address bar', w.calls.replaceState === 1 && w.sb.location.hash === '');
  let r = await w.sb.ocFetch('/config');
  check('B authenticated call returns 200', r.status === 200, r.status);
  check('B no prompt was needed', w.calls.prompt === 0);

  // C: no token stored -> 401 -> prompt -> retry succeeds, token remembered for the session
  w = makeWindow('', [TOKEN]);
  r = await w.sb.ocFetch('/config');
  check('C 401 then prompt then retry = 200', r.status === 200 && w.calls.prompt === 1, `${r.status}/${w.calls.prompt}`);
  r = await w.sb.ocFetch('/config');
  check('C later calls reuse the stored token (no 2nd prompt)', r.status === 200 && w.calls.prompt === 1);

  // D: wrong stored token; two concurrent calls share ONE prompt
  w = makeWindow('#token=wrong-token-wrong-token-wrong-token-1234', [TOKEN]);
  const [r1, r2] = await Promise.all([w.sb.ocFetch('/config'), w.sb.ocFetch('/modules')]);
  check('D concurrent 401s trigger a single prompt', w.calls.prompt === 1, w.calls.prompt);
  check('D both retried successfully', r1.status === 200 && r2.status !== 401, `${r1.status}/${r2.status}`);

  // E: prompt cancelled -> caller sees the 401, stale token discarded
  w = makeWindow('#token=wrong-token-wrong-token-wrong-token-1234', []);
  r = await w.sb.ocFetch('/config');
  check('E cancelled prompt returns the 401', r.status === 401, r.status);
  check('E stale token removed from storage', !('ocbrain_api_token' in w.store));

  // F: SSE through the middleware with the fetch-based reader; unauthenticated probes generate api.auth_denied events
  w = makeWindow('#token=' + encodeURIComponent(TOKEN), []);
  const got = [];
  const stream = w.sb.ocEventStream('/events', m => got.push(m.data));
  await sleep(400);
  for (let i = 0; i < 3; i++) { await fetch(new URL('/config', base)); await sleep(150); }
  await sleep(500);
  const parsed = got.map(d => { try { return JSON.parse(d); } catch (e) { return null; } }).filter(Boolean);
  check('F SSE messages received through the auth middleware', parsed.length >= 3, got.length);
  check('F messages are the audited denials (reason=missing)', parsed.length >= 3 && parsed.every(p => p.reason === 'missing'), JSON.stringify(parsed[0]));
  check('F payload never contains the token', !JSON.stringify(parsed).includes(TOKEN));
  stream.close(); const n = got.length;
  await fetch(new URL('/config', base)); await sleep(600);
  check('F close() stops delivery', got.length === n, `${n}->${got.length}`);

  // G: stream with no token and no prompt answer ends instead of hammering the server
  w = makeWindow('', []);
  let g = 0; const s2 = w.sb.ocEventStream('/events', () => g++);
  await sleep(1500);
  check('G unauthenticated stream gives up quietly', g === 0 && w.calls.prompt === 1, `msgs=${g} prompts=${w.calls.prompt}`);
  s2.close();

  // H: a WRONG token typed into the prompt: one prompt, then quiet (no prompt on every status poll)
  w = makeWindow('', ['wrong-token-wrong-token-wrong-token-1234']);
  r = await w.sb.ocFetch('/config');
  const h2 = await w.sb.ocFetch('/config');
  const h3 = await w.sb.ocFetch('/config');
  check('H wrong token: the rejected call surfaces the 401', r.status === 401, r.status);
  check('H wrong token: later polls do not prompt again', w.calls.prompt === 1 && h2.status === 401 && h3.status === 401, `prompts=${w.calls.prompt}`);
  check('H wrong token: the rejected token is forgotten', !('ocbrain_api_token' in w.store));

  const failed = results.filter(x => !x[1]);
  for (const [n, ok, extra] of results) console.log((ok ? 'PASS ' : 'FAIL ') + n + (extra !== '' ? '  [' + extra + ']' : ''));
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  process.exit(failed.length ? 1 : 0);
})().catch(e => { console.error('HARNESS ERROR', e); process.exit(2); });
