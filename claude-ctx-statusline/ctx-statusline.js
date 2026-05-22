#!/usr/bin/env node
const data = require('fs').readFileSync(0, 'utf8');
const j = JSON.parse(data);
const t = j.context_window?.context_window_size || 200000;
const p = j.context_window?.used_percentage || 0;
const u = Math.floor(p * t / 100 / 1000);
const tk = Math.floor(t / 1000);
const pi = Math.floor(p);
console.log(`Ctx: ${u}k/${tk}k (${pi}%)`);
