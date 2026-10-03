/**
 * Photon Spectrum iMessage adapter (Stable docs).
 * https://photon.codes/docs/spectrum-ts/getting-started
 *
 * Credentials are read from the environment. Without them this process
 * exits and the test chat keeps working.
 */

import { loadMap, resolveRider } from "./resolve.js";

const projectId = process.env.SPECTRUM_PROJECT_ID?.trim();
const projectSecret = process.env.SPECTRUM_PROJECT_SECRET?.trim();

if (!projectId || !projectSecret) {
  console.error("Spectrum iMessage is not connected.");
  console.error(
    "Set SPECTRUM_PROJECT_ID and SPECTRUM_PROJECT_SECRET from the Photon project settings.",
  );
  console.error(
    "Stable docs: https://photon.codes/docs/spectrum-ts/getting-started",
  );
  console.error("The test chat works without these.");
  process.exit(1);
}

const { Spectrum } = await import("spectrum-ts");
const { imessage } = await import("spectrum-ts/providers/imessage");

const senderMap = loadMap(process.env.SPECTRUM_SENDER_MAP || "");
const api = (process.env.COMMUTE_API_URL || "http://127.0.0.1:47291").replace(
  /\/$/,
  "",
);

const app = await Spectrum({
  projectId,
  projectSecret,
  providers: [imessage.config()],
});

console.log("Fareline is listening for iMessage. Ledger:", api);

for await (const [space, message] of app.messages) {
  if (message.direction && message.direction !== "inbound") continue;
  if (message.content?.type !== "text") continue;
  const text = message.content.text?.trim();
  if (!text) continue;

  const rider = resolveRider(message.sender, senderMap);
  if (!rider) {
    const id = message.sender?.id ?? "unknown";
    await space.send(
      `I don't know which rider this iMessage is (${id}). Add them to SPECTRUM_SENDER_MAP. I didn't change the ledger.`,
    );
    continue;
  }

  try {
    const response = await fetch(`${api}/api/messages`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ sender: rider, text, source: "spectrum" }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      await space.send(body.detail || "The ledger couldn't record that.");
      continue;
    }
    await space.send(body.reply);
  } catch (error) {
    console.error(error);
    await space.send("The ledger didn't answer, so I didn't record that message.");
  }
}
