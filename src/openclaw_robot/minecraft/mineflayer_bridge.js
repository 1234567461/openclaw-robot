#!/usr/bin/env node
'use strict';
/**
 * mineflayer 桥接脚本（由 openclaw-robot 的 Python 端 spawn 调用）
 *
 * 职责：
 *   1. ping 服务器探测真实协议版本（解决写死版本号导致连不上 26.x 服务器）
 *   2. 以真实玩家身份登录，把玩家聊天 / 连接事件以 JSON 行打到 stdout
 *   3. 版本号显式指定失败时，自动去掉版本号让 mineflayer 自行协商一次
 *
 * 用法：node mineflayer_bridge.js <host> <port> <username> [version]
 *   version 省略或 "auto" -> 先 ping 探测服务器版本，失败再自动协商
 *
 * stdout 每行一个 JSON：
 *   {"type":"ping",     "version":"1.21.x"}
 *   {"type":"chat",     "user":"Steve", "message":"hi"}
 *   {"type":"spawn"}
 *   {"type":"login",    "version":"..."}
 *   {"type":"kicked",   "reason":"..."}
 *   {"type":"error",    "err":"..."}
 *   {"type":"end",      "reason":"..."}
 */

const [host, portStr, username, versionArg] = process.argv.slice(2);
const port = Number(portStr) || 25565;

function emit(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

let mineflayer;
try {
  mineflayer = require('mineflayer');
} catch (e) {
  emit({ type: 'error', err: 'mineflayer not installed: ' + e.message });
  process.exit(2);
}

function createBot(version) {
  const opts = { host, port, username, auth: 'offline', hideErrors: false };
  if (version && version !== 'auto') {
    opts.version = version;
  } else {
    // 不传 version：让 mineflayer 用自己支持的协议尝试自动协商
    emit({ type: 'auto-version' });
  }

  let bot;
  try {
    bot = mineflayer.createBot(opts);
  } catch (e) {
    emit({ type: 'error', err: 'createBot failed: ' + e.message });
    return;
  }

  let errored = false;
  bot.on('login', () => emit({ type: 'login', version: bot.version }));
  bot.on('spawn', () => {
    emit({ type: 'spawn' });
    try { bot.chat('ClawBot online'); } catch (_) {}
  });
  bot.on('chat', (user, message) => {
    if (user && user !== bot.username) {
      emit({ type: 'chat', user, message });
    }
  });
  bot.on('kicked', (reason) => emit({ type: 'kicked', reason: String(reason) }));
  bot.on('error', (err) => {
    const msg = String((err && err.message) || err);
    emit({ type: 'error', err: msg });
    // 显式版本不对时，回退到自动协商（只回退一次，防止死循环）
    if (!errored && opts.version) {
      errored = true;
      emit({ type: 'retry-auto' });
      try { bot.quit('retry-auto'); } catch (_) {}
      setTimeout(() => createBot(undefined), 500);
    }
  });
  bot.on('end', (reason) => emit({ type: 'end', reason: String(reason) }));
}

async function detectVersion() {
  if (versionArg && versionArg !== 'auto') {
    return versionArg;
  }
  try {
    const mc = require('minecraft-protocol');
    const res = await mc.ping({ host, port });
    const v = res && res.version && res.version.version;
    if (v) emit({ type: 'ping', version: v });
    return v || undefined;
  } catch (e) {
    emit({ type: 'ping-failed', err: String(e.message || e) });
    return undefined;
  }
}

detectVersion().then((v) => createBot(v));
