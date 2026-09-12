import { DiceRoll } from "@dice-roller/rpg-dice-roller"

// Player-facing dice roller behavior. The library is bundled into this file by
// esbuild, so the page issues no runtime network requests. Like every Quartz
// inline component script (Graph, d3), this is concatenated into the global
// postscript.js and shipped on every page, not only the dice-roller page; the
// rpg-dice-roller payload riding along everywhere is an accepted, framework-
// standard size tradeoff, not a per-page split. This script is
// included once per page load; the module-level "nav" listener re-runs on every
// SPA navigation. Because Quartz replaces the page body on navigation, the
// elements queried below are fresh each time, so element-level listeners never
// stack. Any document/window listeners are torn down via window.addCleanup.

const HISTORY_KEY = "althas-dice-history"
const HISTORY_CAP = 20

type HistoryEntry =
  | { kind: "roll"; notation: string; output: string; total: number }
  | { kind: "duality"; hope: number; fear: number; total: number; verdict: string }

function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as HistoryEntry[]).slice(0, HISTORY_CAP) : []
  } catch {
    return []
  }
}

function saveHistory(entries: HistoryEntry[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, HISTORY_CAP)))
  } catch {
    // Storage full or unavailable: history just won't persist, no need to break.
  }
}

// Turn the library's "4d6kh3: [4, 4, 4, 2d] = 12" into just the "[4, 4, 4, 2d]"
// breakdown, so the result card can show notation, breakdown, and total in
// distinct slots without duplicating the total.
function extractBreakdown(output: string): string {
  const afterColon = output.slice(output.indexOf(":") + 1)
  const beforeEquals = afterColon.slice(0, afterColon.lastIndexOf("="))
  return beforeEquals.trim()
}

function makeEl(tag: string, className?: string, text?: string): HTMLElement {
  const el = document.createElement(tag)
  if (className) el.className = className
  if (text !== undefined) el.textContent = text
  return el
}

// Build the compact history row for one entry. All user-influenced strings go
// in via textContent, never innerHTML, so nothing from the notation box can
// inject markup.
function renderHistoryItem(entry: HistoryEntry): HTMLLIElement {
  const li = document.createElement("li")
  li.className = "dice-history-item"

  if (entry.kind === "duality") {
    const verdictClass =
      entry.verdict === "Critical Success!"
        ? "crit"
        : entry.verdict === "with Hope"
          ? "hope"
          : "fear"
    li.classList.add("dice-history-item--duality")
    li.appendChild(makeEl("span", "dice-history-label", "Duality"))
    li.appendChild(makeEl("span", "dice-history-detail", `Hope ${entry.hope}, Fear ${entry.fear}`))
    li.appendChild(
      makeEl("span", `dice-history-verdict dice-verdict--${verdictClass}`, entry.verdict),
    )
    li.appendChild(makeEl("span", "dice-history-total", String(entry.total)))
  } else {
    li.appendChild(makeEl("span", "dice-history-label", entry.notation))
    li.appendChild(makeEl("span", "dice-history-detail", extractBreakdown(entry.output)))
    li.appendChild(makeEl("span", "dice-history-total", String(entry.total)))
  }

  return li
}

// Build the large result card for the newest roll.
function renderResultCard(entry: HistoryEntry): HTMLElement {
  const card = makeEl("div", "dice-result-card")

  if (entry.kind === "duality") {
    const verdictClass =
      entry.verdict === "Critical Success!"
        ? "crit"
        : entry.verdict === "with Hope"
          ? "hope"
          : "fear"
    card.classList.add("dice-result-card--duality")

    const dice = makeEl("div", "dice-duality-dice")
    dice.appendChild(makeEl("span", "dice-die dice-die--hope", `Hope ${entry.hope}`))
    dice.appendChild(makeEl("span", "dice-die dice-die--fear", `Fear ${entry.fear}`))
    card.appendChild(dice)

    card.appendChild(makeEl("div", "dice-result-total", String(entry.total)))
    card.appendChild(makeEl("div", `dice-verdict dice-verdict--${verdictClass}`, entry.verdict))
  } else {
    card.appendChild(makeEl("div", "dice-result-notation", entry.notation))
    card.appendChild(makeEl("div", "dice-result-breakdown", extractBreakdown(entry.output)))
    card.appendChild(makeEl("div", "dice-result-total", String(entry.total)))
  }

  return card
}

function renderError(message: string): HTMLElement {
  return makeEl("div", "dice-result-error", message)
}

function setupDiceRoller() {
  const root = document.querySelector<HTMLElement>(".dice-roller")
  if (!root) return

  const form = root.querySelector<HTMLFormElement>(".dice-notation-row")
  const input = root.querySelector<HTMLInputElement>(".dice-notation-input")
  const resultEl = root.querySelector<HTMLElement>(".dice-result")
  const historyEl = root.querySelector<HTMLOListElement>(".dice-history")
  const clearBtn = root.querySelector<HTMLButtonElement>(".dice-clear-btn")
  const quickButtons = root.querySelectorAll<HTMLButtonElement>(".dice-quick-btn")
  const dualityBtn = root.querySelector<HTMLButtonElement>(".dice-duality-btn")

  if (!form || !input || !resultEl || !historyEl || !clearBtn || !dualityBtn) return

  let history = loadHistory()

  function renderHistory() {
    historyEl!.replaceChildren(...history.map(renderHistoryItem))
    clearBtn!.hidden = history.length === 0
  }

  function commit(entry: HistoryEntry) {
    resultEl!.replaceChildren(renderResultCard(entry))
    history.unshift(entry)
    history = history.slice(0, HISTORY_CAP)
    saveHistory(history)
    renderHistory()
  }

  function rollNotation(notation: string) {
    const trimmed = notation.trim()
    if (!trimmed) return
    try {
      const roll = new DiceRoll(trimmed)
      commit({ kind: "roll", notation: trimmed, output: roll.output, total: roll.total })
    } catch (err) {
      const message = err instanceof Error ? err.message : "That is not a valid dice notation."
      resultEl!.replaceChildren(renderError(message))
    }
  }

  function rollDuality() {
    const hope = new DiceRoll("1d12").total
    const fear = new DiceRoll("1d12").total
    const verdict = hope === fear ? "Critical Success!" : hope > fear ? "with Hope" : "with Fear"
    commit({ kind: "duality", hope, fear, total: hope + fear, verdict })
  }

  const onSubmit = (e: Event) => {
    e.preventDefault()
    rollNotation(input.value)
  }
  // Roll on Enter explicitly rather than relying on implicit form submission.
  // preventDefault stops the implicit submit, so the roll fires exactly once.
  const onKeydown = (e: KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault()
      rollNotation(input.value)
    }
  }
  const onQuick = (e: Event) => {
    const btn = e.currentTarget as HTMLButtonElement
    rollNotation(btn.dataset.notation ?? "")
  }
  const onDuality = () => rollDuality()
  const onClear = () => {
    history = []
    saveHistory(history)
    resultEl.replaceChildren()
    renderHistory()
  }

  form.addEventListener("submit", onSubmit)
  input.addEventListener("keydown", onKeydown)
  quickButtons.forEach((btn) => btn.addEventListener("click", onQuick))
  dualityBtn.addEventListener("click", onDuality)
  clearBtn.addEventListener("click", onClear)

  window.addCleanup(() => {
    form.removeEventListener("submit", onSubmit)
    input.removeEventListener("keydown", onKeydown)
    quickButtons.forEach((btn) => btn.removeEventListener("click", onQuick))
    dualityBtn.removeEventListener("click", onDuality)
    clearBtn.removeEventListener("click", onClear)
  })

  renderHistory()
}

document.addEventListener("nav", () => {
  setupDiceRoller()
})
