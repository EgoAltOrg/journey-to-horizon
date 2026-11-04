import test, { describe } from "node:test"
import assert from "node:assert"
import { SchemaValidator } from "./leafletMapPlugin"

describe("marker schema", () => {
  test("a plain pin still validates", () => {
    assert(SchemaValidator.marker({ coordinates: "432, 496", icon: "lucide-castle" }))
  })

  test("accepts a hex marker with a size", () => {
    assert(SchemaValidator.marker({ coordinates: "432, 496", shape: "hex", size: 48 }))
    assert(SchemaValidator.marker({ coordinates: "432, 496", shape: "pin" }))
  })

  test("rejects an unknown shape or a non-positive size", () => {
    assert(!SchemaValidator.marker({ coordinates: "432, 496", shape: "star" }))
    assert(!SchemaValidator.marker({ coordinates: "432, 496", shape: "hex", size: 0 }))
    assert(!SchemaValidator.marker({ coordinates: "432, 496", shape: "hex", size: "big" }))
  })
})

describe("map schema", () => {
  test("accepts an overlay and a language", () => {
    assert(
      SchemaValidator.map({
        image: "assets/jth-map.svg",
        overlay: "assets/jth-map-rumors.json",
        lang: "pt",
      }),
    )
  })

  test("a map without an overlay still validates", () => {
    assert(SchemaValidator.map({ image: "assets/jth-map.svg" }))
  })

  test("rejects a non-string overlay", () => {
    assert(!SchemaValidator.map({ image: "assets/jth-map.svg", overlay: 3 }))
  })

  test("rejects a language the overlay has no text for", () => {
    assert(SchemaValidator.map({ image: "assets/jth-map.svg", lang: "en" }))
    assert(!SchemaValidator.map({ image: "assets/jth-map.svg", lang: "fr" }))
  })
})
