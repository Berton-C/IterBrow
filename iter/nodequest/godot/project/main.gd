extends Node2D
# NodeQuest Ch1 - puzzle-lab, clean geometric/minimal, single-file slice.

const W := 1280.0
const H := 720.0
const BG := Color("0e1420")
const INK := Color("e8ecf2")
const ACCENT := Color("4fd1c5")
const WARM := Color("ffb454")
const DIM := Color("5a6b7f")

var room := 0
var player_pos := Vector2(200.0, 480.0)
var lamp_lit := false
var door_open := [false, false, false]
var plank_units := [0, 0, 0]
var scale_choice := -1
var obs_collected := 0
var hyp := -1
var test := -1
var msg := ""
var msg_timer := 0.0
var title_timer := 5.0
var target_pos := Vector2(200.0, 480.0)
var has_target := false

func _process(delta: float) -> void:
	var spd := 420.0 * delta
	if Input.is_key_pressed(KEY_RIGHT) or Input.is_key_pressed(KEY_D): player_pos.x += spd
	if Input.is_key_pressed(KEY_LEFT) or Input.is_key_pressed(KEY_A): player_pos.x -= spd
	if Input.is_key_pressed(KEY_UP) or Input.is_key_pressed(KEY_W): player_pos.y -= spd
	if Input.is_key_pressed(KEY_DOWN) or Input.is_key_pressed(KEY_S): player_pos.y += spd
	player_pos.x = clamp(player_pos.x, 60.0, W - 60.0)
	player_pos.y = clamp(player_pos.y, 120.0, H - 60.0)
	if title_timer > 0.0: title_timer -= delta
	if msg_timer > 0.0: msg_timer -= delta
	if has_target:
		var d := target_pos - player_pos
		if d.length() < 12.0: has_target = false
		else: player_pos += d.normalized() * min(spd, d.length())
	if room == 0:
		if door_open[0] and player_pos.x > W - 90.0:
			room = 1; player_pos = Vector2(120.0, 500.0); msg = "UNIT BRIDGE: planks are missing their units."; msg_timer = 4
		if door_open[0] and player_pos.y < 150.0 and player_pos.x > 500.0 and player_pos.x < 780.0:
			room = 2; player_pos = Vector2(160.0, 500.0); msg = "SCALE CHAMBER: where does a galaxy live?"; msg_timer = 4
	elif room == 1 and door_open[1] and player_pos.x > W - 90.0:
		room = 0; player_pos = Vector2(W - 140.0, 480.0)
	queue_redraw()

func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var k: int = event.keycode
		if k >= KEY_1 and k <= KEY_4: _act(k - KEY_1)
		if k == KEY_SPACE: _observe()
		if k == KEY_R and room == 1: plank_units = [0, 0, 0]
		if k == KEY_TAB and room == 2: scale_choice = -1
		if k == KEY_ENTER and room > 0:
			room = 0; player_pos = Vector2(640.0, 480.0)

func _handle_mouse(pos: Vector2) -> void:
	if room == 0 and obs_collected < 3 and pos.distance_to(Vector2(640.0, 520.0)) < 130.0:
		_observe(); return
	if pos.y > 610.0:
		_act(int(clamp((pos.x - 60.0) / 300.0, 0, 3))); return
	target_pos = Vector2(clamp(pos.x, 60.0, W - 60.0), clamp(pos.y, 120.0, H - 60.0))
	has_target = true

func _observe() -> void:
	if room == 0 and obs_collected < 3 and player_pos.distance_to(Vector2(640.0, 520.0)) < 130.0:
		obs_collected += 1
		msg = "Observation %d/3: switch up, wires intact, filament dark." % obs_collected
		if obs_collected == 3: msg = "Three observations logged. HYPOTHESIS panel appeared (left)."
		msg_timer = 3

func _act(n: int) -> void:
	match room:
		0: _act_hyp(n)
		1: _act_units(n)
		2: _act_scale(n)

func _act_hyp(n: int) -> void:
	if obs_collected < 3:
		msg = "Observe the lamp first (SPACE near it)."
		msg_timer = 2
		return
	if hyp == -1:
		if n <= 2:
			hyp = n + 1
			msg = "Hypothesis chosen. Now pick a TEST (1-3 in the panel)."
			msg_timer = 2.5
		return
	if test == -1 and n <= 2:
		test = n + 1
		if hyp == 3 and test == 2:
			lamp_lit = true; door_open[0] = true
			msg = "CONFIRMED - new bulb glows, light floods the lab. Doors unlocked (right & up)!"
			msg_timer = 6
		else:
			msg = "The lamp hums, unconvinced. Prediction didn't match observation. Try again."
			msg_timer = 3
			hyp = -1; test = -1

func _act_units(n: int) -> void:
	# n: 0=km 1=m 2=s 3=kg ; correct = m, km, kg
	for i in range(3):
		if plank_units[i] == 0 and player_pos.distance_to(Vector2(340.0 + i*300.0, 560.0)) < 160.0:
			plank_units[i] = n + 1
			break
	var correct := [2, 1, 4]
	var all_set := true
	var ok := true
	for i in range(3):
		if plank_units[i] == 0: all_set = false
		elif plank_units[i] != correct[i]: ok = false
	if all_set:
		if ok:
			door_open[1] = true
			msg = "Units align - bridge solidifies. Exit (right) unlocked!"
			msg_timer = 5
		else:
			msg = "A plank wobbles, drops its unit. Press R to reset."
			msg_timer = 3
			plank_units = [0, 0, 0]

func _act_scale(n: int) -> void:
	if scale_choice != -1: return
	if n <= 2:
		scale_choice = n
		if n == 0:
			door_open[2] = true
			msg = "Correct - zooming OUT to galactic scale... portal glows. CH1 COMPLETE!"
			msg_timer = 7
		else:
			msg = "That's not where galaxies live. TAB to un-zoom, try again."
			msg_timer = 4

func _t(pos: Vector2, s: String, c: Color, size: int) -> void:
	draw_string(ThemeDB.fallback_font, pos, s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, c)

func _draw_door(c: Vector2, open: bool, label: String, up := false) -> void:
	var col := ACCENT if open else DIM
	if up:
		draw_rect(Rect2(c.x - 40, c.y - 30, 80, 60), col)
		draw_rect(Rect2(c.x - 40, c.y - 30, 80, 60), BG, false, 2.0)
		_t(c + Vector2(-38, 40), label, col, 14)
	else:
		draw_rect(Rect2(c.x - 25, c.y - 60, 50, 120), col)
		draw_rect(Rect2(c.x - 25, c.y - 60, 50, 120), BG, false, 2.0)
		_t(c + Vector2(-24, 80), label, col, 14)

func _draw() -> void:
	draw_rect(Rect2(0, 0, W, H), BG)
	if room == 0: _draw_lab()
	elif room == 1: _draw_gate()
	else: _draw_zoom()
	draw_circle(player_pos, 16.0, INK)
	draw_arc(player_pos, 22.0, 0.0, TAU, 48, ACCENT, 2.0)
	_t(Vector2(30, 40), "NODEQUEST  CH 1  PUZZLE LAB", INK, 28)
	var hints := "WASD move  SPACE observe  1-4 choose  R reset planks  ENTER back to hub"
	_t(Vector2(30, 68), hints, DIM, 16)
	if msg_timer > 0.0:
		_t(Vector2(40, H - 36), msg, WARM, 19)
	if title_timer > 0.0:
		_t(Vector2(W/2 - 330, H/2 - 60), "A lamp is dark. Doors need knowledge.", ACCENT, 34)
		_t(Vector2(W/2 - 300, H/2 - 10), "WASD/arrows to walk. SPACE near the lamp.", INK, 21)

func _draw_lab() -> void:
	var lamp := Vector2(640.0, 520.0)
	draw_circle(lamp, 40.0, WARM if lamp_lit else Color("223042"))
	draw_arc(lamp, 48.0, 0.0, TAU, 48, WARM, 3.0)
	_t(lamp + Vector2(-36, -76), "LAMP", INK, 18)
	if not lamp_lit:
		draw_arc(lamp, 64.0 + 8.0 * sin(Time.get_ticks_msec() / 300.0), 0.0, TAU, 48, ACCENT, 1.5)
	var p := Vector2(50.0, 130.0)
	draw_rect(Rect2(p, Vector2(540.0, 340.0)), Color("141b28"))
	draw_rect(Rect2(p, Vector2(540.0, 340.0)), DIM, false, 1.0)
	_t(p + Vector2(18, 36), "HYPOTHESIS EXPERIMENT", ACCENT, 21)
	if obs_collected < 3:
		_t(p + Vector2(18, 72), "Observe the lamp first: %d / 3" % obs_collected, INK, 19)
	else:
		var hs := ["bulb burned out", "a ghost blows it out", "switch breaks circuit"]
		_t(p + Vector2(18, 72), "WHY is it dark? (press 1-3)", INK, 19)
		for i in 3:
			_t(p + Vector2(18, 102 + i*26), ("> " if hyp == i+1 else "  ") + hs[i], WARM if hyp == i+1 else INK, 18)
		if hyp != -1:
			var ts := ["stare at it", "swap bulb, does it light?", "read its biography"]
			_t(p + Vector2(18, 190), "TEST IT (press 1-3)", INK, 19)
			for i in 3:
				_t(p + Vector2(18, 220 + i*26), ("> " if test == i+1 else "  ") + ts[i], WARM if test == i+1 else INK, 18)
		if lamp_lit:
			_t(p + Vector2(18, 300), "Confirmed: circuit fixed. Light!", ACCENT, 18)
	_draw_door(Vector2(W - 60, 480), door_open[0], "1>BRIDGE")
	_draw_door(Vector2(640, 110), door_open[0], "2>SCALE", true)

func _draw_gate() -> void:
	_t(Vector2(50, 110), "UNIT BRIDGE - each plank is a number missing its unit", INK, 20)
	var labels := ["300 cm? m? km?", "1000 m? km?", "30 g? kg?"]
	var names := ["km", "m", "s", "kg"]
	for i in 3:
		var c := Vector2(340.0 + i*300.0, 560.0)
		var col := ACCENT if plank_units[i] > 0 else DIM
		draw_rect(Rect2(c.x - 110, c.y - 18, 220, 36), col)
		draw_rect(Rect2(c.x - 110, c.y - 18, 220, 36), BG, false, 2.0)
		var s: String = labels[i] if plank_units[i] == 0 else labels[i].split(" ")[0] + " " + names[plank_units[i]-1]
		_t(c + Vector2(-100, 8), s, INK, 19)
	_t(Vector2(50, 150), "Stand on a plank, press its unit: 1 km  2 m  3 s  4 kg", DIM, 17)
	if door_open[1]:
		_draw_door(Vector2(W - 60, 480), true, "EXIT")
	else:
		draw_rect(Rect2(W - 85, 420, 50, 120), DIM)

func _draw_zoom() -> void:
	_t(Vector2(50, 110), "SCALE CHAMBER - choose the scale where a GALAXY lives", INK, 20)
	var cols := [Color("8ab6ff"), ACCENT, Color("c58cff")]
	var chosen := scale_choice
	var names := ["PLANET", "STAR", "GALAXY"]
	for i in 3:
		var c := Vector2(240.0 + i*360.0, 400.0)
		var act := chosen == i
		draw_circle(c, 90.0 if act else 60.0, cols[i] if act else Color("1a2334"))
		draw_arc(c, 90.0 if act else 60.0, 0.0, TAU, 48, cols[i] if act else DIM, 3.0)
		_t(c + Vector2(-34, 8), names[i], INK, 20)
		_t(c + Vector2(-20, 130), "(press %d)" % (i+1), DIM, 16)
	if door_open[2]:
		_t(Vector2(500, 660), "CHAPTER 1 COMPLETE - portal glows!", ACCENT, 24)
