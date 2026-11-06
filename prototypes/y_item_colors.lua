-- Factorio items have no color of their own. Mods that color things by the item they carry, and
-- machines that tint by their recipe, read a recipe's crafting_machine_tint instead. Without one,
-- such mods fall back to an ingredient, which miscolors items made from unrelated materials:
-- UC-A2 came out yellow from contaminated water, orange stuff blue from Y-res1 dust.
-- Gives every recipe making these items the average color of the item's icon, unless the recipe
-- has a tint. Items made from them (Quantrinum, dry mud, conductive wire...) follow. Runs at the
-- end of data-updates, before other mods read the colors in data-final-fixes, and again after
-- Yuoki's integrations add their recipes.
local colors = {
  ["y-c_mud"] = { r = 0.27, g = 0.18, b = 0.13 },
  ["y-chip-1"] = { r = 0.16, g = 0.34, b = 0.51 },
  ["y-crystal-cnd"] = { r = 0.66, g = 0.51, b = 0.11 },
  ["y-crystal2"] = { r = 0.13, g = 0.70, b = 0.67 },
  ["y-dirt"] = { r = 0.27, g = 0.22, b = 0.18 },
  ["y-fame"] = { r = 0.93, g = 0.53, b = 0.22 },
  ["y-infused-uca2"] = { r = 0.80, g = 0.34, b = 0.85 },
  ["y-orange-stuff"] = { r = 0.50, g = 0.27, b = 0.11 },
  ["y-quantrinum"] = { r = 0.58, g = 0.39, b = 0.99 },
  ["y-richdust"] = { r = 0.54, g = 0.17, b = 0.32 },
  ["y-unicomp-a2"] = { r = 0.48, g = 0.17, b = 0.38 },
  ["y_chip_plate"] = { r = 0.33, g = 0.44, b = 0.29 },
  ["y_crystal2_combined"] = { r = 0.25, g = 0.62, b = 0.84 },
  ["y_quantrinum_infused"] = { r = 0.87, g = 0.75, b = 0.99 },
}

local function makes(recipe, item)
  if recipe.main_product then
    return recipe.main_product == item
  end
  local results = recipe.results or {}
  return #results == 1 and results[1].type == "item" and results[1].name == item
end

return function()
  for _, recipe in pairs(data.raw.recipe) do
    if not recipe.crafting_machine_tint then
      for item, color in pairs(colors) do
        if makes(recipe, item) then
          recipe.crafting_machine_tint = { primary = color }
          break
        end
      end
    end
  end
end
