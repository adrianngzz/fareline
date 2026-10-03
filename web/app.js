const app = document.querySelector("#app");
const colors = {
  Adrian: "#0c6b4d",
  Alex: "#8a3d12",
  Sam: "#1d4e89",
  Riley: "#6b3fa0",
  Fareline: "#1c1612",
};

let sender = "Adrian";
let draft = "";
let shellReady = false;

boot();

async function boot() {
  renderLoading();
  try {
    fill(await getState());
  } catch {
    renderError("The ledger didn't answer. Nothing on screen is live yet.", boot);
  }
}

async function getState() {
  const response = await fetch("/api/state");
  if (!response.ok) throw new Error("state");
  return response.json();
}

function renderLoading() {
  shellReady = false;
  app.dataset.state = "loading";
  app.replaceChildren();
  const section = document.createElement("section");
  section.className = "boot";
  section.innerHTML = `
    <p class="eyebrow">Ledger</p>
    <h1>Opening today's carpool ledger…</h1>
    <div class="skeleton" aria-hidden="true"><span></span><span></span><span></span></div>
  `;
  app.append(section);
}

function renderError(message, retry) {
  shellReady = false;
  app.dataset.state = "error";
  app.replaceChildren();
  const section = document.createElement("section");
  section.className = "error-panel";
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "Couldn't reach Fareline";
  const title = document.createElement("h1");
  title.textContent = "The carpool ledger is offline.";
  const copy = document.createElement("p");
  copy.textContent = message;
  const button = document.createElement("button");
  button.className = "retry";
  button.type = "button";
  button.textContent = "Try again";
  button.addEventListener("click", retry);
  section.append(eyebrow, title, copy, button);
  app.append(section);
}

function ensureShell() {
  if (shellReady) return;
  app.replaceChildren();
  app.dataset.state = "ready";
  const layout = document.createElement("div");
  layout.className = "layout";
  layout.innerHTML = `
    <section class="chat" aria-label="Group thread">
      <div class="panel-head">
        <h2>Intern carpool</h2>
        <p class="day" id="day"></p>
      </div>
      <div class="thread" id="thread"></div>
      <form class="composer" id="composer">
        <div class="speakers" id="speakers" role="group" aria-label="Who is speaking"></div>
        <div class="row">
          <input id="text" name="text" autocomplete="off" maxlength="500" placeholder="I paid $48, Alex and Sam rode." aria-label="Message">
          <button class="primary" id="send" type="submit">Send</button>
        </div>
        <p class="status" id="status"></p>
      </form>
    </section>
    <aside class="ledger" aria-label="Running balances">
      <div class="panel-head">
        <h2>Who owes whom</h2>
        <p class="open-total" id="open-total"></p>
      </div>
      <ul class="rsvps" id="rsvps"></ul>
      <p class="nets-title">Open balances</p>
      <ul class="nets" id="nets"></ul>
      <div class="even-block" id="even-block"></div>
      <p class="note">Even split, to the cent. The payer's own share is already covered.</p>
    </aside>
  `;
  app.append(layout);
  document.querySelector("#composer").addEventListener("submit", onSubmit);
  document.querySelector("#text").addEventListener("input", (event) => {
    draft = event.target.value;
  });
  shellReady = true;
}

function fill(state) {
  ensureShell();
  app.dataset.state = state.messages.length ? "ready" : "empty";
  document.querySelector("#day").textContent = state.today_label;
  document.querySelector("#text").value = draft;
  renderSpeakers(state.people);
  renderThread(state);
  renderLedger(state);
  setBusy(false, "");
}

function renderSpeakers(people) {
  const box = document.querySelector("#speakers");
  box.replaceChildren();
  const known = people.some((person) => person.name === sender);
  if (!known && people[0]) sender = people[0].name;
  for (const person of people) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "speaker";
    button.setAttribute("aria-pressed", person.name === sender ? "true" : "false");
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.style.background = colorFor(person.name);
    const label = document.createElement("span");
    label.textContent = person.name;
    button.append(dot, label);
    button.addEventListener("click", () => {
      sender = person.name;
      renderSpeakers(people);
    });
    box.append(button);
  }
}

function renderThread(state) {
  const thread = document.querySelector("#thread");
  thread.replaceChildren();
  if (!state.messages.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    const title = document.createElement("h3");
    title.textContent = "No rides on the ledger yet.";
    const copy = document.createElement("p");
    copy.textContent = "Pick who is speaking. Say you're in, name who rode after you paid, or ask what you owe.";
    empty.append(title, copy);
    thread.append(empty);
    return;
  }
  for (const message of state.messages) {
    const bubble = document.createElement("article");
    bubble.className = `bubble ${message.kind}`;
    const who = document.createElement("div");
    who.className = "who";
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.style.background = colorFor(message.sender);
    const name = document.createElement("strong");
    name.textContent = message.sender;
    const time = document.createElement("span");
    time.className = "time";
    time.textContent = formatTime(message.created_at);
    who.append(dot, name, time);
    const body = document.createElement("p");
    body.className = "body";
    body.textContent = message.body;
    bubble.append(who, body);
    thread.append(bubble);
  }
  thread.scrollTop = thread.scrollHeight;
}

function renderLedger(state) {
  const rsvps = document.querySelector("#rsvps");
  rsvps.replaceChildren();
  for (const person of state.people) {
    const item = document.createElement("li");
    const status = person.rsvp || "no rsvp";
    item.className = `chip ${person.rsvp || ""}`;
    item.textContent = `${person.name} · ${status === "in" ? "in today" : status === "out" ? "out today" : "no RSVP"}`;
    rsvps.append(item);
  }

  const nets = document.querySelector("#nets");
  nets.replaceChildren();
  const total = state.nets.reduce((sum, net) => sum + net.cents, 0);
  document.querySelector("#open-total").textContent = total
    ? `Open ${formatCents(total)}`
    : "All even";

  if (!state.nets.length) {
    const item = document.createElement("li");
    item.className = "even-row";
    item.textContent = "No balances yet. The first fare shows up here.";
    nets.append(item);
  } else {
    for (const net of state.nets) {
      const item = document.createElement("li");
      item.className = "net";
      const label = document.createElement("span");
      label.textContent = `${net.debtor} owes ${net.creditor}`;
      const amount = document.createElement("strong");
      amount.textContent = net.amount;
      item.append(label, amount);
      nets.append(item);
    }
  }

  const even = state.people.filter((person) => person.even);
  const block = document.querySelector("#even-block");
  block.replaceChildren();
  if (state.nets.length && even.length) {
    const title = document.createElement("h3");
    title.textContent = "Even";
    const line = document.createElement("p");
    line.textContent = even.length === 1
      ? `${even[0].name} is even with everyone.`
      : `${join(even.map((person) => person.name))} are even with everyone.`;
    block.append(title, line);
  }
}

async function onSubmit(event) {
  event.preventDefault();
  const text = draft.trim();
  if (!sender) {
    setBusy(false, "Pick who is speaking.", true);
    return;
  }
  if (!text) {
    setBusy(false, "Write a message first.", true);
    return;
  }
  setBusy(true, "Writing the ledger…");
  try {
    const response = await fetch("/api/messages", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ sender, text, source: "test_chat" }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setBusy(false, body.detail || "The ledger couldn't record that.", true);
      return;
    }
    draft = "";
    fill(body.state);
  } catch {
    setBusy(false, "The ledger didn't answer. Your message was not recorded.", true);
  }
}

function setBusy(busy, message, isError = false) {
  const form = document.querySelector("#composer");
  const status = document.querySelector("#status");
  const send = document.querySelector("#send");
  if (!form || !status || !send) return;
  form.setAttribute("aria-busy", busy ? "true" : "false");
  send.disabled = busy;
  document.querySelector("#text").disabled = busy;
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function colorFor(name) {
  if (colors[name]) return colors[name];
  let hash = 0;
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) % 360;
  return `hsl(${hash} 42% 32%)`;
}

function formatTime(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
  }).format(date);
}

function formatCents(cents) {
  const sign = cents < 0 ? "-" : "";
  const absolute = Math.abs(cents);
  const dollars = Math.floor(absolute / 100);
  const remainder = String(absolute % 100).padStart(2, "0");
  return `${sign}$${dollars}.${remainder}`;
}

function join(names) {
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, -1).join(", ")}, and ${names[names.length - 1]}`;
}
