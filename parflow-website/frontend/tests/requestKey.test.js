import test from 'node:test';
import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { requestKey } from '../src/utils/requestKey.js';

test('LAN HTTP without randomUUID still generates unique UUIDv4 request keys', () => {
  const httpCrypto = { getRandomValues: bytes => webcrypto.getRandomValues(bytes) };
  const keys = Array.from({ length: 1000 }, () => requestKey(httpCrypto));
  assert.equal(new Set(keys).size, keys.length);
  for (const key of keys) assert.match(key, /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/);
});
test('uses native randomUUID when available', () => {
  assert.equal(requestKey({ randomUUID: () => 'native-key' }), 'native-key');
});
