-- luacheck: globals script game
-- Run with each value of yuoki-prod-mod-behaviour in an isolated engine scenario.
local machines = {}
local restricted

script.on_init(function()
  restricted = settings.startup["yuoki-prod-mod-behaviour"].value
  local surface = game.surfaces[1]
  surface.request_to_generate_chunks({ 0, 0 }, 1)
  surface.force_generate_chunk_requests()
  local function machine(x, recipe, name)
    local entity = assert(surface.create_entity({
      name = name or "assembling-machine-3",
      position = { x, 0 },
      force = "player",
    }))
    entity.set_recipe(recipe)
    return entity
  end
  local chest = machine(0, "wooden-chest")
  local modules = chest.get_module_inventory()
  for _, name in ipairs({ "y-pink-module-1", "y-pink-module-2", "y-pink-module-3", "y_modul_science" }) do
    assert(modules.can_insert({ name = name, count = 1 }) == not restricted, name)
  end
  for _, name in ipairs({ "productivity-module", "productivity-module-2", "productivity-module-3" }) do
    assert(not modules.can_insert({ name = name, count = 1 }), name .. " became unrestricted")
  end
  for _, name in ipairs({ "speed-module", "efficiency-module" }) do
    assert(modules.can_insert({ name = name, count = 1 }), name .. " lost access")
  end
  if not restricted then
    assert(modules.insert({ name = "y_modul_science", count = 1 }) == 1)
  end
  chest.get_inventory(defines.inventory.crafter_input).insert({ name = "wood", count = 40 })
  machines[#machines + 1] = { entity = chest, expected = restricted and 20 or 25 }

  local plain = machine(5, "wooden-chest")
  plain.get_inventory(defines.inventory.crafter_input).insert({ name = "wood", count = 40 })
  machines[#machines + 1] = { entity = plain, expected = 20 }

  local cable = machine(10, "copper-cable")
  for _, name in ipairs({ "productivity-module", "y-pink-module-1", "y_modul_science" }) do
    assert(cable.get_module_inventory().can_insert({ name = name, count = 1 }), name .. " lost copper cable access")
  end

  if script.active_mods["yuoki-category-fixture"] then
    for i, category in ipairs({ "yuoki-test-pink", "productivity" }) do
      for j, recipe in ipairs({ "copper-cable", "wooden-chest" }) do
        local entity = machine(15 + (i * 2 + j) * 5, recipe, "yuoki-test-" .. category)
        local inventory = entity.get_module_inventory()
        for k, name in ipairs({ "y-pink-module-1", "y-pink-module-2", "y-pink-module-3", "y_modul_science" }) do
          local matches_machine = (k <= 2) == (category == "yuoki-test-pink")
          local expected = matches_machine and (recipe == "copper-cable" or not restricted)
          assert(
            inventory.can_insert({ name = name, count = 1 }) == expected,
            entity.name .. "/" .. recipe .. "/" .. name
          )
        end
      end
    end
    log("YUOKI ORIGINAL MACHINE CATEGORIES PASS")
  end
end)

script.on_event(defines.events.on_tick, function(event)
  for _, test in ipairs(machines) do
    test.entity.energy = 10000000
  end
  if event.tick == 600 then
    for _, test in ipairs(machines) do
      local count = test.entity.get_output_inventory().get_item_count("wooden-chest")
      assert(count == test.expected, "Expected " .. test.expected .. " chests, got " .. count)
      assert(test.entity.get_inventory(defines.inventory.crafter_input).is_empty())
    end
    log("YUOKI PRODUCTIVITY PASS: restricted=" .. tostring(restricted))
    script.finish_test(true)
  end
end)
