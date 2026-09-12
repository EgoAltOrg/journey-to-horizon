import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
// @ts-ignore
import script from "./scripts/dice.inline"
import style from "./styles/dice.scss"
import { classNames } from "../util/lang"

// The player-facing dice roller. This component only renders the static shell
// (inputs, buttons, empty result and history containers); all behavior lives in
// dice.inline.ts, which bundles the MIT @dice-roller/rpg-dice-roller library at
// build time so the page makes zero external requests at runtime. It is wired
// into the layout behind a slug check (see quartz.layout.ts) so it appears only
// on the dice-roller page.
const QUICK_DICE = ["d4", "d6", "d8", "d10", "d12", "d20", "d100"]

export default (() => {
  const DiceRoller: QuartzComponent = ({ displayClass }: QuartzComponentProps) => {
    return (
      <div class={classNames(displayClass, "dice-roller")}>
        <form class="dice-notation-row" autocomplete="off">
          <input
            type="text"
            class="dice-notation-input"
            placeholder="e.g. 2d20+3, 4d6kh3, 3d8+2d6"
            aria-label="Dice notation"
            spellcheck={false}
          />
          <button type="submit" class="dice-btn dice-roll-btn">
            Roll
          </button>
        </form>

        <div class="dice-quick-rolls" role="group" aria-label="Quick rolls">
          {QUICK_DICE.map((die) => (
            <button type="button" class="dice-btn dice-quick-btn" data-notation={"1" + die}>
              {die}
            </button>
          ))}
          <button type="button" class="dice-btn dice-duality-btn">
            Duality Dice
          </button>
        </div>

        <div class="dice-result" aria-live="polite"></div>

        <div class="dice-history-block">
          <div class="dice-history-head">
            <h2 class="dice-history-title">History</h2>
            <button type="button" class="dice-btn dice-clear-btn" hidden>
              Clear history
            </button>
          </div>
          <ol class="dice-history"></ol>
        </div>
      </div>
    )
  }

  DiceRoller.css = style
  DiceRoller.afterDOMLoaded = script

  return DiceRoller
}) satisfies QuartzComponentConstructor
