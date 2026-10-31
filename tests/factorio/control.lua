-- luacheck: globals script game prototypes helpers yi
-- Run as a local scenario with Yuoki and optional official expansion mods enabled.
require("__Yuoki__/lib/yi-tools")

local failures = {}
local generators = {}
local function check(name, fn)
  local surface = game.create_surface("test-" .. name, { width = 64, height = 64 })
  surface.request_to_generate_chunks({ 0, 0 }, 1)
  surface.force_generate_chunk_requests()
  local ok, err = pcall(fn, surface)
  if not ok then
    failures[#failures + 1] = name .. ": " .. tostring(err)
  end
  game.delete_surface(surface)
end

local function create(surface, name, x, y)
  return assert(surface.create_entity({ name = name, position = { x or 0, y or 0 }, force = "player" }))
end

script.on_init(function()
  local quality = prototypes.quality.legendary and "legendary" or "normal"
  check("ground", function(surface)
    local ground = surface.create_entity({
      name = "item-on-ground",
      position = { 0, 0 },
      stack = { name = "y-slag", count = 10, quality = quality },
    })
    yi.lib.migration.global_replace_item("y-slag", "stone")
    assert(ground.valid and ground.stack.name == "stone" and ground.stack.count == 10)
    assert(ground.stack.quality.name == quality)
  end)
  check("belt", function(surface)
    local belt = create(surface, "transport-belt")
    local line = belt.get_transport_line(1)
    for _, position in ipairs({ 0.1, 0.35, 0.6, 0.85 }) do
      assert(line.insert_at(position, { name = "y-slag", count = 1, quality = quality }))
    end
    local positions = {}
    for i = 1, #line do
      positions[i] = line.get_item_position(i)
    end
    yi.lib.migration.global_replace_item("y-slag", "stone")
    assert(#line == 4)
    for i = 1, #line do
      assert(line[i].name == "stone" and line[i].quality.name == quality)
      assert(line.get_item_position(i) == positions[i])
    end
  end)
  check("inventory", function(surface)
    local chest = create(surface, "steel-chest")
    local inventory = chest.get_inventory(defines.inventory.chest)
    inventory.insert({ name = "y-slag", count = 10, quality = quality })
    yi.lib.migration.global_replace_item("y-slag", "stone")
    assert(inventory.get_item_count({ name = "stone", quality = quality }) == 10)
    assert(inventory.get_item_count({ name = "y-slag", quality = quality }) == 0)
  end)
  check("smaller-stacks", function(surface)
    local chest = create(surface, "steel-chest")
    chest.get_inventory(defines.inventory.chest)[1].set_stack({ name = "y-slag", count = 100, quality = quality })
    yi.lib.migration.global_replace_item("y-slag", "wooden-chest")
    local total = chest.get_item_count({ name = "wooden-chest", quality = quality })
    for _, entity in pairs(surface.find_entities_filtered({ type = "item-entity" })) do
      assert(entity.stack.name == "wooden-chest" and entity.stack.quality.name == quality)
      total = total + entity.stack.count
    end
    assert(total == 100)
  end)
  check("inserter", function(surface)
    local inserter = create(surface, "inserter")
    inserter.set_filter(1, { name = "y-slag", quality = quality, comparator = ">=" })
    inserter.held_stack.set_stack({ name = "y-slag", count = 1, quality = quality })
    yi.lib.migration.global_replace_item("y-slag", "stone")
    local filter = inserter.get_filter(1)
    assert(filter.name == "stone" and filter.quality == quality and filter.comparator == "≥")
    assert(inserter.held_stack.name == "stone" and inserter.held_stack.quality.name == quality)
  end)
  check("requests", function(surface)
    local chest = create(surface, "requester-chest")
    local sections = chest.get_logistic_sections()
    local section = sections.get_section(1) or sections.add_section()
    section.set_slot(
      1,
      { value = { type = "item", name = "y-slag", quality = quality, comparator = "=" }, min = 50, max = 100 }
    )
    yi.lib.migration.global_replace_item("y-slag", "stone")
    local filter = section.get_slot(1)
    assert(filter.value.name == "stone" and filter.value.quality == quality)
    assert(filter.min == 50 and filter.max == 100)
  end)
  check("storage", function(surface)
    local chest = create(surface, "storage-chest")
    chest.storage_filter = { name = "y-slag", quality = quality }
    yi.lib.migration.global_replace_item("y-slag", "stone")
    assert(chest.storage_filter.name.name == "stone" and chest.storage_filter.quality.name == quality)
  end)
  check("splitters", function(surface)
    local splitter = create(surface, "splitter")
    for _, replace in ipairs({ yi.lib.migration.global_replace_item, yi.lib.migration.fix_splitters }) do
      splitter.splitter_filter = { name = "y-slag", quality = quality, comparator = ">=" }
      splitter.splitter_output_priority = "right"
      replace("y-slag", "stone")
      local filter = splitter.splitter_filter
      assert(filter.name == "stone" and filter.quality == quality and filter.comparator == "≥")
      assert(splitter.splitter_output_priority == "right")
    end
  end)
  check("signals", function(surface)
    local combinator = create(surface, "constant-combinator")
    local control = combinator.get_or_create_control_behavior()
    local section = control.get_section(1) or control.add_section()
    for i, signal in ipairs({ { "virtual", "signal-A" }, { "fluid", "water" }, { "item", "iron-plate" } }) do
      section.set_slot(
        i,
        { value = { type = signal[1], name = signal[2], quality = "normal", comparator = "=" }, min = i * 10 }
      )
    end
    local before = helpers.table_to_json(section.filters)
    yi.lib.migration.bulk_replace({ ["y-slag"] = "stone" })
    assert(helpers.table_to_json(section.filters) == before)
  end)
  check("fluids", function(surface)
    local pipe = create(surface, "pipe")
    local other = create(surface, "pipe", 1)
    assert(pipe.get_fluid_segment_id(1) == other.get_fluid_segment_id(1))
    local amount = pipe.set_fluid_segment_fluid(1, { name = "water", amount = 150, temperature = 25 })
    yi.lib.migration.global_replace_fluid("water", "crude-oil")
    local fluid = pipe.get_fluid_segment_fluid(1)
    assert(fluid.name == "crude-oil" and fluid.amount == amount and fluid.temperature == 25)
    assert(other.get_fluid_segment_fluid(1).name == "crude-oil")
  end)
  check("filtered-fluids", function(surface)
    local pump = create(surface, "pump", 10)
    assert(pump.set_fluid_filter(1, "water"))
    assert(pump.set_fluid(1, { name = "water", amount = 40, temperature = 25 }) == 40)
    local pipes = { create(surface, "pipe"), create(surface, "pipe", 1), create(surface, "pipe", 2) }
    assert(pipes[1].set_fluid_filter(1, "water"))
    assert(pipes[3].set_fluid_filter(1, "water"))
    assert(pipes[2].set_fluid_segment_fluid(1, { name = "water", amount = 150, temperature = 25 }) == 150)
    local target = create(surface, "pipe", 3)
    assert(target.set_fluid_filter(1, "crude-oil"))
    assert(target.set_fluid_segment_fluid(1, { name = "crude-oil", amount = 40, temperature = 25 }) == 40)
    assert(pipes[2].get_fluid_segment_fluid(1).amount == 150)
    yi.lib.migration.global_replace_fluid("water", "crude-oil")
    local fluid = pump.get_fluid(1)
    assert(pump.get_fluid_filter(1).name == "crude-oil")
    assert(fluid.name == "crude-oil" and fluid.amount == 40 and fluid.temperature == 25)
    for _, pipe in ipairs(pipes) do
      fluid = pipe.get_fluid_segment_fluid(1)
      assert(fluid.name == "crude-oil" and fluid.amount == 190 and fluid.temperature == 25)
      assert(pipe.get_fluid_segment_id(1) == pipes[1].get_fluid_segment_id(1))
    end
    assert(pipes[1].get_fluid_filter(1).name == "crude-oil")
    assert(pipes[3].get_fluid_filter(1).name == "crude-oil")
    assert(target.get_fluid_segment_id(1) == pipes[1].get_fluid_segment_id(1))
  end)
  check("fixed-fluid-filter", function(surface)
    local pipe = create(surface, "pipe", -10)
    assert(pipe.set_fluid_segment_fluid(1, { name = "water", amount = 30, temperature = 25 }) == 30)
    local pump = create(surface, "pump")
    assert(pump.set_fluid_filter(1, "water"))
    assert(pump.set_fluid(1, { name = "water", amount = 40, temperature = 25 }) == 40)
    local boiler = create(surface, "boiler", 10)
    assert(boiler.set_fluid_segment_fluid(1, { name = "water", amount = 80, temperature = 25 }) == 80)
    local ok = pcall(yi.lib.migration.global_replace_fluid, "water", "crude-oil")
    assert(not ok)
    assert(pipe.get_fluid_segment_fluid(1).name == "water" and pipe.get_fluid_segment_fluid(1).amount == 30)
    assert(pump.get_fluid_filter(1).name == "water")
    assert(pump.get_fluid(1).name == "water" and pump.get_fluid(1).amount == 40)
    assert(boiler.get_fluid_segment_filter(1).name == "water")
    assert(boiler.get_fluid_segment_fluid(1).name == "water" and boiler.get_fluid_segment_fluid(1).amount == 80)
  end)
  check("prototypes", function()
    assert(settings.startup["yuoki-prod-mod-behaviour"])
    assert(prototypes.entity.y_hppump.module_inventory_size == 1)
    local expected = { normal = 1, uncommon = 1.15, rare = 1.25, epic = 1.35, legendary = 1.45 }
    for _, name in ipairs({
      "y_crusher2",
      "y_formpress2",
      "y-dirtwasher",
      "y_mc_dirtwasher",
      "y-alien-infuser",
      "y-atomic-constructor",
      "y-atomic-quantum-composer",
    }) do
      for q, multiplier in pairs(expected) do
        if prototypes.quality[q] then
          assert(
            math.abs(prototypes.entity[name].energy_usage_quality_multiplier[q] - multiplier) < 0.0001,
            name .. " " .. q
          )
        end
      end
    end
  end)
  local surface = game.create_surface("generator-test", { width = 512, height = 128 })
  surface.request_to_generate_chunks({ 0, 0 }, 4)
  surface.force_generate_chunk_requests()
  local cases = {
    { "y-steam-turbine", "steam", 100, 165 },
    { "y-obninsk-turbine", "steam", 150, 165 },
    { "y-notfall-generator-s2", "steam", 100, 165 },
    { "y_steam_turbine_mc", "steam", 100, 165 },
    { "y_steam_turbine_gr", "steam", 100, 165 },
    { "y-seg", "y-mechanical-force", 70, 150 },
    { "y-seg-p", "y-mechanical-force", 70, 150 },
    { "y-meg-s", "y-mechanical-force", 50, 150 },
    { "y-beg", "y-mechanical-force", 70, 150 },
    { "y-heg", "y-mechanical-force", 70, 150 },
  }
  for i, case in ipairs(cases) do
    local name, fluid, minimum, hot = table.unpack(case)
    local x = (i - 5) * 30
    local generator = create(surface, name, x)
    create(surface, "substation", x + 5)
    local load = create(surface, "electric-energy-interface", x + 5, 5)
    load.power_production = 0
    load.power_usage = 10000000
    load.electric_buffer_size = 10000000
    generators[#generators + 1] = {
      entity = generator,
      initial = generator.set_fluid(1, { name = fluid, amount = 200, temperature = minimum - 1 }),
      fluid = fluid,
      hot = hot,
      energy = 0,
    }
  end
end)

script.on_event(defines.events.on_tick, function(event)
  for _, test in ipairs(generators) do
    test.energy = test.energy + test.entity.energy_generated_last_tick
  end
  if event.tick == 120 then
    for _, test in ipairs(generators) do
      if test.energy ~= 0 or test.entity.get_fluid(1).amount ~= test.initial then
        failures[#failures + 1] = test.entity.name .. " consumed fluid below its minimum"
      end
      test.entity.set_fluid(1, { name = test.fluid, amount = 200, temperature = test.hot })
      test.energy = 0
    end
  elseif event.tick == 240 then
    for _, test in ipairs(generators) do
      if test.energy <= 0 then
        failures[#failures + 1] = test.entity.name .. " did not generate above its minimum"
      end
    end
    for _, failure in ipairs(failures) do
      log("FAIL " .. failure)
    end
    log("YUOKI REGRESSION FAILURES: " .. #failures)
    script.finish_test(#failures == 0)
  end
end)
