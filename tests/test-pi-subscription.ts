// Tests for dot-pi/agent/extensions/pi-subscription.ts (the footer's plan usage and sent time).
// Run: node --test tests/test-pi-subscription.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import init, { clock, footerText, usageFromMessage } from "../dot-pi/agent/extensions/pi-subscription.ts";

const at = (h: number, m: number, s = 0, day = 17) => new Date(2026, 10, day, h, m, s).getTime();
const rateLimit = (unifiedWindows: unknown) => ({
	role: "assistant",
	provider: "claude-code",
	diagnostics: [
		{ type: "claude-code.turn-relay", details: {} },
		{ type: "claude-code.rate-limit", details: { status: "allowed", rateLimitType: "seven_day", unifiedWindows } },
	],
});

test("reads unifiedWindows from the claude-code rate-limit diagnostic", () => {
	const w = { seven_day: { utilization: 0.15, resetsAt: 1795341600 } };
	assert.deepEqual(usageFromMessage(rateLimit(w)), w);
	assert.equal(usageFromMessage({ role: "assistant", diagnostics: [] }), undefined);
	assert.equal(usageFromMessage(rateLimit(undefined)), undefined);
});

test("shows five-hour and weekly usage with reset times, and the sent time to the second", () => {
	const now = at(14, 3, 27);
	const text = footerText({
		subscription: "work",
		usage: {
			five_hour: { utilization: 0.123, resetsAt: at(17, 0) / 1000 },
			seven_day: { utilization: 0.01, resetsAt: at(9, 0, 0, 20) / 1000 },
		},
		sentAt: now,
		now,
	});
	assert.equal(text, "subscription: work · 5h 12% ↻17:00 · week 1% ↻Fri 09:00 · sent 14:03:27");
});

test("a plan without a five-hour window shows only the week", () => {
	const now = at(10, 0);
	const text = footerText({ subscription: "personal", usage: { seven_day: { utilization: 0.15, resetsAt: at(12, 0) / 1000 } }, now });
	assert.equal(text, "subscription: personal · week 15% ↻12:00");
});

test("without a personal login the name is left out but usage and time still show", () => {
	assert.equal(footerText({ sentAt: at(8, 5, 9) }), "sent 08:05:09");
	assert.equal(footerText({}), undefined);
	assert.equal(clock(at(23, 59, 1)), "23:59:01");
});

test("the extension updates the footer on user messages and claude-code replies", async () => {
	const handlers: Record<string, Function> = {};
	init({ on: (e: string, h: Function) => (handlers[e] = h), registerCommand() {} } as any);
	const statuses: (string | undefined)[] = [];
	const ctx = {
		hasUI: true,
		ui: { setStatus: (_k: string, t: string | undefined) => statuses.push(t) },
		sessionManager: {
			getBranch: () => [
				{ type: "message", message: { role: "user", timestamp: at(9, 1, 2) } },
				{ type: "message", message: rateLimit({ seven_day: { utilization: 0.5 } }) },
			],
		},
	};
	await handlers.session_start({}, ctx);
	assert.match(statuses.at(-1)!, /week 50% · sent 09:01:02$/);
	await handlers.message_start({ message: { role: "user", timestamp: at(9, 30, 45) } }, ctx);
	assert.match(statuses.at(-1)!, /sent 09:30:45$/);
	await handlers.message_end({ message: { ...rateLimit({ five_hour: { utilization: 0.2 }, seven_day: { utilization: 0.6 } }), provider: "openai" } }, ctx);
	assert.match(statuses.at(-1)!, /week 50%/);
	await handlers.message_end({ message: rateLimit({ five_hour: { utilization: 0.2 }, seven_day: { utilization: 0.6 } }) }, ctx);
	assert.match(statuses.at(-1)!, /5h 20% · week 60% · sent 09:30:45$/);
});
