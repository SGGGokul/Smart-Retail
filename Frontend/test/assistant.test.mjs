import test from "node:test";
import assert from "node:assert/strict";

import { resolveAssistantQuery } from "../lib/assistant.ts";
import {
  calculateShelfStatus,
  getInventorySummary,
  getRestockPrioritySummary,
} from "../lib/inventory.ts";
import { shelves, alerts } from "../lib/mock-data.ts";

test("Inventory Thresholds & Produce classification", async (t) => {
  await t.test("Threshold boundaries follow canonical rules (<40% crit, 40-70% low, >70% ok)", () => {
    assert.equal(calculateShelfStatus(26), "critical");
    assert.equal(calculateShelfStatus(38), "critical");
    assert.equal(calculateShelfStatus(39), "critical");
    assert.equal(calculateShelfStatus(40), "low");
    assert.equal(calculateShelfStatus(58), "low");
    assert.equal(calculateShelfStatus(70), "low");
    assert.equal(calculateShelfStatus(71), "ok");
    assert.equal(calculateShelfStatus(84), "ok");
    assert.equal(calculateShelfStatus(92), "ok");
  });

  await t.test("Produce (71% fill) is strictly optimal and never flagged for restock", () => {
    const produce = shelves.find((s) => s.name === "Produce");
    assert.ok(produce, "Produce shelf must exist");
    assert.equal(produce.fillPct, 71);
    assert.equal(calculateShelfStatus(produce.fillPct), "ok");
  });

  await t.test("Canonical inventory summary has exactly 3 restock bays in strict severity order", () => {
    const summary = getInventorySummary(shelves);

    assert.equal(summary.restockCount, 3, "Exactly 3 zones must require restocking");
    assert.equal(summary.criticalCount, 2, "Exactly 2 zones must be critical");
    assert.equal(summary.lowStockCount, 1, "Exactly 1 zone must be low stock");
    assert.equal(summary.optimalCount, 3, "Exactly 3 zones must be optimal");

    // Bakery (26%) must precede Beverages (38%)
    assert.equal(summary.restockBays[0].name, "Bakery");
    assert.equal(summary.restockBays[0].fillPct, 26);
    assert.equal(summary.restockBays[1].name, "Beverages");
    assert.equal(summary.restockBays[1].fillPct, 38);
    assert.equal(summary.restockBays[2].name, "Dairy");
    assert.equal(summary.restockBays[2].fillPct, 58);

    // Produce must NOT be in restock bays
    const produceInRestock = summary.restockBays.some((s) => s.name === "Produce");
    assert.equal(produceInRestock, false, "Produce must never be in restock bays");
  });

  await t.test("Restock priority summary returns correct label and sorted names", () => {
    const prio = getRestockPrioritySummary(shelves);
    assert.equal(prio.count, 3);
    assert.equal(prio.label, "3 zones");
    assert.ok(prio.details.includes("Bakery (26%)"));
    assert.ok(prio.details.includes("Beverages (38%)"));
    assert.ok(prio.details.includes("Dairy (58%)"));
  });
});

test("Assistant Intent Routing & Fallback (P0 Bug Fixes)", async (t) => {
  await t.test("Typing 'hi' returns greeting, NEVER restocking or inventory", () => {
    const greetings = ["hi", "Hi", "HI", "hello", "Hello", "hey", "Hey", "good morning", "yo"];

    for (const g of greetings) {
      const res = resolveAssistantQuery(g);
      assert.equal(res.category, "greetings", `Expected greetings for "${g}", got "${res.category}"`);
      assert.ok(res.text.toLowerCase().includes("retailiq copilot") || res.text.toLowerCase().includes("hello"), "Greeting must introduce assistant");
      assert.ok(!res.text.toLowerCase().includes("aisle restocking audit"), "Greeting must never return restocking audit");
      assert.ok(!res.text.toLowerCase().includes("bakery (aisle 7)"), "Greeting must not mention bakery fill");
      assert.equal(res.structuredInventory, undefined, "Greeting must not attach structured inventory");
      assert.ok(res.suggestedFollowUps.length > 0, "Greeting must provide quick follow-up queries");
    }
  });

  await t.test("Unknown or unsupported queries return helpful capabilities fallback, NEVER restocking", () => {
    const unknowns = [
      "What is the weather in Seattle?",
      "Can you play chess?",
      "Who is the CEO?",
      "xyz123abc",
    ];

    for (const u of unknowns) {
      const res = resolveAssistantQuery(u);
      assert.equal(res.category, "fallback", `Expected fallback for "${u}", got "${res.category}"`);
      assert.ok(res.text.includes("could not find telemetry records"), "Fallback must explain query mismatch");
      assert.ok(res.text.includes("Customer traffic"), "Fallback must suggest customer traffic");
      assert.ok(res.text.includes("Shelf inventory"), "Fallback must suggest shelf inventory");
      assert.ok(res.text.includes("Checkout queue"), "Fallback must suggest queues");
      assert.ok(!res.text.toLowerCase().includes("aisle restocking audit"), "Fallback must never return restocking audit");
      assert.equal(res.structuredInventory, undefined, "Fallback must not attach structured inventory");
    }
  });

  await t.test("Restocking query returns structured inventory with severity sorting", () => {
    const res = resolveAssistantQuery("Which shelves need restocking?", shelves);
    assert.equal(res.category, "inventory");
    assert.ok(res.structuredInventory, "Structured inventory must be present");
    assert.equal(res.structuredInventory.length, 3);
    assert.equal(res.structuredInventory[0].name, "Bakery");
    assert.equal(res.structuredInventory[0].fillPct, 26);
    assert.equal(res.structuredInventory[0].status, "critical");

    assert.equal(res.structuredInventory[1].name, "Beverages");
    assert.equal(res.structuredInventory[1].fillPct, 38);
    assert.equal(res.structuredInventory[1].status, "critical");

    assert.equal(res.structuredInventory[2].name, "Dairy");
    assert.equal(res.structuredInventory[2].fillPct, 58);
    assert.equal(res.structuredInventory[2].status, "low");

    // Text must cite 3 zones
    assert.ok(res.text.includes("exactly 3 zones"));
    assert.ok(res.text.includes("optimal availability (>70%)"));
  });

  await t.test("Starter prompt: 'Which shelves need restocking first?' identifies Bakery (26%) as #1", () => {
    const res = resolveAssistantQuery("Which shelves need restocking first?", shelves);
    assert.equal(res.category, "inventory");
    assert.ok(res.text.includes("Bakery in Aisle 7 needs restocking first"));
    assert.ok(res.text.includes("26% fill"));
    assert.ok(res.structuredInventory);
    assert.equal(res.structuredInventory[0].name, "Bakery");
  });

  await t.test("Starter prompt: 'Why did the latest critical shelf alert trigger?' explains Aisle 4 drop", () => {
    const res = resolveAssistantQuery("Why did the latest critical shelf alert trigger?");
    assert.equal(res.category, "alerts");
    assert.ok(res.text.includes("al-01"));
    assert.ok(res.text.includes("Aisle 4 (Beverages)"));
    assert.ok(res.text.includes("38%"));
    assert.ok(res.text.includes("critical threshold of 40%"));
  });

  await t.test("Starter prompt: 'Which aisle has the longest checkout queue?' identifies Lane 3", () => {
    const res = resolveAssistantQuery("Which aisle has the longest checkout queue?");
    assert.equal(res.category, "queue");
    assert.ok(res.text.includes("Lane 3"));
    assert.ok(res.text.includes("6.8 min"));
  });

  await t.test("Customer traffic queries return visitor footfall data", () => {
    const res = resolveAssistantQuery("How many customers visited today?");
    assert.equal(res.category, "traffic");
    assert.ok(res.text.includes("1,248 visitors"));
    assert.ok(res.text.includes("+6.2%"));
  });

  await t.test("Checkout queue queries return register bottleneck data", () => {
    const res = resolveAssistantQuery("What is the longest checkout queue?");
    assert.equal(res.category, "queue");
    assert.ok(res.text.includes("Standard Lane 3"));
    assert.ok(res.text.includes("6.8 min"));
  });

  await t.test("Alerts queries return active unacknowledged incidents", () => {
    const res = resolveAssistantQuery("Summarize today's alerts.");
    assert.equal(res.category, "alerts");
    assert.ok(res.text.includes("exactly 3 unacknowledged alerts"));
  });
});

test("Store Alerts Consistency", () => {
  const unacknowledged = alerts.filter((a) => !a.acknowledged);
  assert.equal(unacknowledged.length, 3, "Total active unacknowledged alerts must be exactly 3");
});
