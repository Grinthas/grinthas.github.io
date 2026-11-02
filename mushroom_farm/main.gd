extends Node2D
# Грибная ферма: вид сверху, фермер ходит по пещере.
# Всё (мир, джойстик, магазин) создаётся кодом, картинки лежат в папке assets/.

# ---------- Данные (механика и сохранения такие же, как раньше) ----------

# Виды грибов. Чтобы добавить новый, допиши ещё одну строку.
# grow - секунд роста, price - монет за продажу, unlock - цена открытия (0 - открыт сразу).
# shape - форма шляпки (a, b или c, см. картинки shroom_*), glow - светится, когда созрел.
# Новые грибы добавляй только В КОНЕЦ списка, иначе перепутаются старые сохранения.
const MUSHROOMS := [
	{"name": "Шампиньон", "grow": 5.0, "price": 2, "unlock": 0, "color": Color(0.95, 0.9, 0.8), "shape": "a"},
	{"name": "Светящийся гриб", "grow": 12.0, "price": 6, "unlock": 30, "color": Color(0.5, 0.95, 0.95), "shape": "b", "glow": true},
	{"name": "Лисичка", "grow": 25.0, "price": 14, "unlock": 120, "color": Color(1.0, 0.65, 0.2), "shape": "c"},
	{"name": "Лунный гриб", "grow": 50.0, "price": 32, "unlock": 400, "color": Color(0.72, 0.62, 1.0), "shape": "a", "glow": true},
	{"name": "Золотой гриб", "grow": 90.0, "price": 70, "unlock": 1200, "color": Color(1.0, 0.85, 0.25), "shape": "b"},
	{"name": "Кристальный гриб", "grow": 150.0, "price": 130, "unlock": 3000, "color": Color(1.0, 0.5, 0.9), "shape": "c", "glow": true},
]
const LUCKY_CHANCE := 0.12            # шанс двойного урожая при сборе

const SAVE_PATH := "user://save.json"
const START_PLOTS := 4
const MAX_PLOTS := 8

# ---------- Настройки мира и управления ----------

const TILE := 16                      # размер клетки в пикселях картинки
const MAP_W := 14                     # размер пещеры в клетках
const MAP_H := 16
const ZOOM := 4.0                     # во сколько раз увеличиваем пиксели (целое число!)
const SPEED := 52.0                   # скорость фермера, пикселей картинки в секунду
const REACH := 22.0                   # как близко надо подойти к грядке
const PLOT_COLS := [4, 9]             # в каких клетках стоят грядки (два столбца)
const PLOT_ROW0 := 3                  # первая строка грядок
const PLOT_ROW_STEP := 2              # через сколько клеток следующая строка

const JOY_CENTER := Vector2(110, 820)
const JOY_RADIUS := 80.0
const ACT_CENTER := Vector2(440, 820)
const ACT_RADIUS := 72.0
const NO_ID := -99                    # "палец не нажат"

# Украшения пещеры. block - можно ли пройти сквозь. Картинка берётся из assets/<tex>.png
const DECOR := [
	{"tex": "stalagmite", "tile": Vector2i(2, 2), "block": true},
	{"tex": "stalagmite", "tile": Vector2i(12, 13), "block": true},
	{"tex": "stalagmite", "tile": Vector2i(1, 11), "block": true},
	{"tex": "crystal_blue", "tile": Vector2i(11, 3), "block": true},
	{"tex": "crystal_blue", "tile": Vector2i(2, 8), "block": true},
	{"tex": "crystal_pink", "tile": Vector2i(12, 7), "block": true},
	{"tex": "crystal_pink", "tile": Vector2i(6, 14), "block": true},
	{"tex": "barrel", "tile": Vector2i(12, 2), "block": true},
	{"tex": "barrel", "tile": Vector2i(1, 13), "block": true},
]
# Плоские пятна на полу (по ним можно ходить).
const DECALS := [
	{"tex": "puddle", "tile": Vector2i(6, 11)}, {"tex": "puddle", "tile": Vector2i(3, 12)},
	{"tex": "puddle", "tile": Vector2i(10, 12)}, {"tex": "pebbles", "tile": Vector2i(7, 2)},
	{"tex": "pebbles", "tile": Vector2i(5, 9)}, {"tex": "pebbles", "tile": Vector2i(11, 11)},
	{"tex": "moss", "tile": Vector2i(2, 5)}, {"tex": "moss", "tile": Vector2i(11, 9)},
	{"tex": "moss", "tile": Vector2i(8, 13)},
]
# Факелы на стенах (мерцают).
const TORCHES := [Vector2i(3, 0), Vector2i(10, 0), Vector2i(0, 6), Vector2i(13, 10), Vector2i(0, 13)]
const FIREFLIES := 10

const FONT_PATH := "res://fonts/PressStart2P-Regular.ttf"

var coins: int = 0
var unlocked: Array = [true, false, false, false, false, false]  # по числу грибов
var selected: int = 0
var plot_count: int = START_PLOTS
var plots: Array = []  # у каждой грядки: {"type": -1 или номер гриба, "planted_at": время посадки}

var tex := {}                         # картинки по имени
var shroom_tex: Array = []            # shroom_tex[вид гриба][стадия 0..2]
var font: FontFile

var ground: Node2D
var objects: Node2D
var player: Node2D
var player_sprite: Sprite2D
var marker: Sprite2D
var camera: Camera2D
var plot_nodes: Array = []            # {"bed", "shroom", "rock"} для каждой грядки
var plot_state: Array = []            # 0 - пусто/растёт, 1 - созрел (для анимации)
var decor_rects: Array = []           # где нельзя ходить из-за украшений
var crystal_sprites: Array = []
var torch_sprites: Array = []
var fx: Node2D
var time_s: float = 0.0

var hud: CanvasLayer
var coins_label: Label
var seed_label: Label
var toast_label: Label
var toast_tween: Tween
var controls: Control
var shop: Control
var shop_list: VBoxContainer

var joy_id: int = NO_ID
var joy_vec := Vector2.ZERO
var act_id: int = NO_ID
var target: int = -1                  # какая грядка рядом (-1 - никакой)
var walk_time: float = 0.0
var touch_ui: bool = false


func _ready() -> void:
	touch_ui = DisplayServer.is_touchscreen_available()
	_load_game()
	_load_assets()
	_build_world()
	_build_hud()
	_refresh_all()
	var timer := Timer.new()
	timer.wait_time = 0.5
	timer.autostart = true
	timer.timeout.connect(_update_plots)
	add_child(timer)


# ---------- Картинки и шрифт ----------

func _load_assets() -> void:
	for n in ["farmer", "bed", "rock", "marker", "coin", "wall", "torch_1", "torch_2",
			"floor_a", "floor_b", "floor_c", "floor_d"]:
		tex[n] = load("res://assets/%s.png" % n)
	for d in DECOR:
		tex[d["tex"]] = load("res://assets/%s.png" % d["tex"])
	for d in DECALS:
		tex[d["tex"]] = load("res://assets/%s.png" % d["tex"])
	# Гриб рисуем розовой шляпкой, а в игре перекрашиваем в цвет конкретного гриба.
	for m in MUSHROOMS:
		var stages: Array = []
		for s in 3:
			# форма a: shroom_1.png, форма b: shroom_b_1.png, форма c: shroom_c_1.png
			var file := "shroom_%d" % (s + 1) if m["shape"] == "a" else "shroom_%s_%d" % [m["shape"], s + 1]
			stages.append(_tinted(load("res://assets/%s.png" % file), m["color"]))
		shroom_tex.append(stages)
	font = load(FONT_PATH)
	# Без сглаживания, чтобы буквы остались чёткими пикселями.
	font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	font.hinting = TextServer.HINTING_NONE
	font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED


func _tinted(src: Texture2D, col: Color) -> Texture2D:
	var img: Image = src.get_image()
	img.convert(Image.FORMAT_RGBA8)
	for y in img.get_height():
		for x in img.get_width():
			var c := img.get_pixel(x, y)
			if c.a > 0.5 and c.r > 0.98 and c.g < 0.02 and c.b > 0.98:
				img.set_pixel(x, y, col)
	return ImageTexture.create_from_image(img)


func _sprite(t: Texture2D, foot_offset: Vector2) -> Sprite2D:
	# Точка спрайта - его "ноги", так грядки и фермер правильно перекрывают друг друга.
	var s := Sprite2D.new()
	s.texture = t
	s.centered = false
	s.offset = foot_offset
	return s


# ---------- Мир ----------

func _build_world() -> void:
	ground = Node2D.new()
	ground.draw.connect(_draw_ground)
	add_child(ground)

	objects = Node2D.new()
	objects.y_sort_enabled = true
	add_child(objects)

	for i in MAX_PLOTS:
		var root := Node2D.new()
		root.position = Vector2(_plot_tile(i)) * TILE + Vector2(TILE / 2.0, TILE)
		var bed := _sprite(tex["bed"], Vector2(-8, -16))
		var shroom := _sprite(null, Vector2(-8, -16))
		var rock := _sprite(tex["rock"], Vector2(-8, -16))
		root.add_child(bed)
		root.add_child(shroom)
		root.add_child(rock)
		objects.add_child(root)
		plot_nodes.append({"bed": bed, "shroom": shroom, "rock": rock})
		plot_state.append(0)

	for d in DECOR:
		var t: Vector2i = d["tile"]
		var spr := _sprite(tex[d["tex"]], Vector2(-8, -16))
		spr.position = Vector2(t) * TILE + Vector2(TILE / 2.0, TILE)
		objects.add_child(spr)
		if d["block"]:
			decor_rects.append(Rect2(t.x * TILE + 3, t.y * TILE + 6, TILE - 6, TILE - 6))
		if String(d["tex"]).begins_with("crystal"):
			crystal_sprites.append(spr)

	for t in TORCHES:
		var torch := _sprite(tex["torch_1"], Vector2.ZERO)
		torch.position = Vector2(t) * TILE
		torch.z_index = 1
		add_child(torch)
		torch_sprites.append(torch)

	player = Node2D.new()
	player.position = Vector2(7 * TILE, 12 * TILE)
	player_sprite = _sprite(tex["farmer"], Vector2(-8, -16))
	player.add_child(player_sprite)
	objects.add_child(player)

	fx = Node2D.new()      # светлячки
	fx.z_index = 50
	fx.draw.connect(_draw_fireflies)
	add_child(fx)

	marker = _sprite(tex["marker"], Vector2(-4, -4))
	marker.z_index = 100
	marker.visible = false
	add_child(marker)

	camera = Camera2D.new()
	camera.zoom = Vector2(ZOOM, ZOOM)
	camera.limit_left = 0
	camera.limit_right = MAP_W * TILE
	camera.limit_top = -24       # запас под верхнюю панель
	camera.limit_bottom = MAP_H * TILE + 28   # запас под джойстик
	add_child(camera)
	camera.position = player.position
	camera.make_current()


func _draw_ground() -> void:
	for y in MAP_H:
		for x in MAP_W:
			var t: Texture2D
			if x == 0 or y == 0 or x == MAP_W - 1 or y == MAP_H - 1:
				t = tex["wall"]
			elif (x * 7 + y * 13) % 5 == 0:
				t = tex["floor_b"]
			elif (x * 11 + y * 3) % 9 == 0:
				t = tex["floor_c"]
			elif (x * 5 + y * 17) % 13 == 0:
				t = tex["floor_d"]
			else:
				t = tex["floor_a"]
			ground.draw_texture(t, Vector2(x, y) * TILE)
	for d in DECALS:
		ground.draw_texture(tex[d["tex"]], Vector2(d["tile"]) * TILE)


func _plot_tile(i: int) -> Vector2i:
	return Vector2i(PLOT_COLS[i % 2], PLOT_ROW0 + (i >> 1) * PLOT_ROW_STEP)


func _plot_rect(i: int) -> Rect2:
	var t := _plot_tile(i)
	return Rect2(t.x * TILE, t.y * TILE + 3, TILE, TILE - 3)


func _plot_center(i: int) -> Vector2:
	var t := _plot_tile(i)
	return Vector2(t.x * TILE + 8, t.y * TILE + 10)


func _blocked(pos: Vector2) -> bool:
	# Ноги фермера - маленький прямоугольник 8x5.
	var feet := Rect2(pos.x - 4, pos.y - 5, 8, 5)
	var floor_rect := Rect2(TILE, TILE, (MAP_W - 2) * TILE, (MAP_H - 2) * TILE)
	if not floor_rect.encloses(feet):
		return true
	for i in MAX_PLOTS:       # и грядки, и завалы (ещё закрытые грядки) мешают пройти
		if feet.intersects(_plot_rect(i)):
			return true
	for r in decor_rects:     # сталагмиты, кристаллы, бочки
		if feet.intersects(r):
			return true
	return false


func _move_player(dir: Vector2, delta: float) -> void:
	var step := dir * SPEED * delta
	var p := player.position
	if not _blocked(Vector2(p.x + step.x, p.y)):
		p.x += step.x
	if not _blocked(Vector2(p.x, p.y + step.y)):
		p.y += step.y
	player.position = p


func _find_target() -> int:
	var body := player.position + Vector2(0, -5)
	var best := -1
	var best_d := REACH
	for i in plot_count:
		var d := body.distance_to(_plot_center(i))
		if d < best_d:
			best_d = d
			best = i
	return best


# ---------- Каждый кадр ----------

func _process(delta: float) -> void:
	time_s += delta
	_animate_world()
	var dir := _keyboard_dir() + joy_vec
	if dir.length() > 1.0:
		dir = dir.normalized()
	if shop.visible:
		dir = Vector2.ZERO
	if dir != Vector2.ZERO:
		_move_player(dir, delta)
		walk_time += delta
		if absf(dir.x) > 0.1:
			player_sprite.flip_h = dir.x < 0.0
	else:
		walk_time = 0.0
	player_sprite.position.y = -1.0 if (dir != Vector2.ZERO and int(walk_time * 8.0) % 2 == 0) else 0.0
	camera.position = player.position.round() + Vector2(0, -8)

	target = _find_target()
	marker.visible = target >= 0 and not shop.visible
	if target >= 0:
		marker.position = _plot_center(target) + Vector2(0, -16 + (1 if int(Time.get_ticks_msec() / 250.0) % 2 == 0 else 0))
	controls.queue_redraw()


func _animate_world() -> void:
	# Факелы мерцают, кристаллы переливаются, зрелые грибы качаются или светятся.
	for i in torch_sprites.size():
		torch_sprites[i].texture = tex["torch_%d" % (1 if (int(time_s * 5.0) + i) % 2 == 0 else 2)]
	for i in crystal_sprites.size():
		var k := 0.5 + 0.5 * sin(time_s * 2.5 + i * 1.7)
		crystal_sprites[i].modulate = Color.WHITE.lerp(Color(1.5, 1.5, 1.5), k * 0.8)
	for i in MAX_PLOTS:
		var shroom: Sprite2D = plot_nodes[i]["shroom"]
		if plot_state[i] == 1:
			var type: int = plots[i]["type"]
			if MUSHROOMS[type].get("glow", false):
				var g := 0.5 + 0.5 * sin(time_s * 4.0 + i)
				shroom.modulate = Color.WHITE.lerp(Color(1.7, 1.7, 1.7), g)
			else:
				shroom.position.y = -1.0 if int(time_s * 3.0 + i) % 2 == 0 else 0.0
		else:
			shroom.modulate = Color.WHITE
			shroom.position.y = 0.0
	fx.queue_redraw()


func _draw_fireflies() -> void:
	for i in FIREFLIES:
		var base := Vector2(24 + (i * 53) % 150, 30 + (i * 97) % 200)
		var pos := base + Vector2(sin(time_s * (0.5 + i * 0.07) + i) * 10.0, cos(time_s * (0.4 + i * 0.05) + i * 2.0) * 8.0)
		var a := 0.5 + 0.5 * sin(time_s * 2.0 + i * 1.3)
		if a < 0.25:
			continue
		pos = pos.floor()
		fx.draw_rect(Rect2(pos - Vector2(1, 1), Vector2(3, 3)), Color(0.8, 1.0, 0.4, 0.15 * a))
		fx.draw_rect(Rect2(pos, Vector2(1, 1)), Color(1.0, 1.0, 0.6, a))


func _keyboard_dir() -> Vector2:
	var v := Vector2.ZERO
	if Input.is_physical_key_pressed(KEY_A) or Input.is_physical_key_pressed(KEY_LEFT):
		v.x -= 1.0
	if Input.is_physical_key_pressed(KEY_D) or Input.is_physical_key_pressed(KEY_RIGHT):
		v.x += 1.0
	if Input.is_physical_key_pressed(KEY_W) or Input.is_physical_key_pressed(KEY_UP):
		v.y -= 1.0
	if Input.is_physical_key_pressed(KEY_S) or Input.is_physical_key_pressed(KEY_DOWN):
		v.y += 1.0
	return v


# ---------- Ввод: джойстик, кнопка действия, клавиатура ----------

func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		_pointer(event.index, event.position, event.pressed)
	elif event is InputEventScreenDrag:
		_pointer_move(event.index, event.position)
	elif not touch_ui and event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		_pointer(-1, event.position, event.pressed)
	elif not touch_ui and event is InputEventMouseMotion:
		_pointer_move(-1, event.position)
	elif event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode in [KEY_SPACE, KEY_E, KEY_ENTER, KEY_KP_ENTER]:
			_do_action()
		elif event.physical_keycode == KEY_ESCAPE:
			_set_shop(false)


func _pointer(id: int, pos: Vector2, pressed: bool) -> void:
	if pressed:
		if shop.visible:
			return
		if joy_id == NO_ID and pos.distance_to(JOY_CENTER) <= JOY_RADIUS * 1.3:
			joy_id = id
			_pointer_move(id, pos)
		elif act_id == NO_ID and pos.distance_to(ACT_CENTER) <= ACT_RADIUS * 1.2:
			act_id = id
			_do_action()
	else:
		if id == joy_id:
			joy_id = NO_ID
			joy_vec = Vector2.ZERO
		if id == act_id:
			act_id = NO_ID


func _pointer_move(id: int, pos: Vector2) -> void:
	if id != joy_id:
		return
	var v := (pos - JOY_CENTER) / JOY_RADIUS
	if v.length() > 1.0:
		v = v.normalized()
	joy_vec = v if v.length() > 0.2 else Vector2.ZERO


# ---------- Действия игрока ----------

func _do_action() -> void:
	if shop.visible or target < 0:
		return
	var p: Dictionary = plots[target]
	if p["type"] == -1:
		p["type"] = selected
		p["planted_at"] = _now()
		_toast("Посажен: " + MUSHROOMS[selected]["name"])
	elif _is_ripe(p):
		var price: int = MUSHROOMS[p["type"]]["price"]
		var lucky := randf() < LUCKY_CHANCE
		if lucky:
			price *= 2
		coins += price
		p["type"] = -1
		_toast(("Повезло! двойной урожай +%d" if lucky else "+%d монет") % price)
	else:
		var m: Dictionary = MUSHROOMS[p["type"]]
		_toast("Ещё %d сек" % ceili(m["grow"] - (_now() - p["planted_at"])))
		return
	_save_game()
	_refresh_all()


func _on_select_pressed(i: int) -> void:
	if unlocked[i]:
		selected = i
	elif coins >= MUSHROOMS[i]["unlock"]:
		coins -= MUSHROOMS[i]["unlock"]
		unlocked[i] = true
		selected = i
	_save_game()
	_refresh_all()


func _on_dig_pressed() -> void:
	if plot_count >= MAX_PLOTS or coins < _dig_cost():
		return
	coins -= _dig_cost()
	plot_count += 2
	while plots.size() < plot_count:
		plots.append({"type": -1, "planted_at": 0.0})
	_toast("Открыто 2 грядки!")
	_save_game()
	_refresh_all()


func _set_shop(on: bool) -> void:
	shop.visible = on
	if on:
		joy_id = NO_ID
		joy_vec = Vector2.ZERO
		act_id = NO_ID
		_refresh_shop()


# ---------- Интерфейс ----------

func _flat(bg: Color, border: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.set_border_width_all(4)
	s.set_corner_radius_all(0)
	s.content_margin_left = 12
	s.content_margin_right = 12
	s.content_margin_top = 10
	s.content_margin_bottom = 10
	return s


func _make_theme() -> Theme:
	var th := Theme.new()
	th.default_font = font
	th.default_font_size = 16
	var border := Color(0.18, 0.11, 0.07)
	th.set_stylebox("normal", "Button", _flat(Color(0.55, 0.35, 0.18), border))
	th.set_stylebox("hover", "Button", _flat(Color(0.62, 0.40, 0.21), border))
	th.set_stylebox("pressed", "Button", _flat(Color(0.40, 0.25, 0.12), border))
	th.set_stylebox("disabled", "Button", _flat(Color(0.25, 0.2, 0.17), border))
	th.set_stylebox("panel", "PanelContainer", _flat(Color(0.16, 0.12, 0.1), Color(0.55, 0.35, 0.18)))
	th.set_color("font_color", "Button", Color(1, 0.96, 0.85))
	th.set_color("font_hover_color", "Button", Color(1, 1, 1))
	th.set_color("font_pressed_color", "Button", Color(1, 1, 1))
	th.set_color("font_disabled_color", "Button", Color(0.55, 0.5, 0.45))
	return th


func _label(text: String, size := 16, color := Color(1, 0.96, 0.85)) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


func _button(text: String, min_h := 64) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(0, min_h)
	b.focus_mode = Control.FOCUS_NONE
	return b


func _build_hud() -> void:
	hud = CanvasLayer.new()
	hud.layer = 10
	add_child(hud)

	var ui := Control.new()
	ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.theme = _make_theme()
	hud.add_child(ui)

	# Верхняя панель
	var bar := ColorRect.new()
	bar.color = Color(0.08, 0.05, 0.04, 0.85)
	bar.position = Vector2.ZERO
	bar.size = Vector2(540, 92)
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(bar)

	var coin := TextureRect.new()
	coin.texture = tex["coin"]
	coin.stretch_mode = TextureRect.STRETCH_SCALE
	coin.position = Vector2(16, 14)
	coin.size = Vector2(32, 32)     # 8x8 -> 32x32, ровно x4
	coin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(coin)

	coins_label = _label("", 24, Color(1, 0.85, 0.3))
	coins_label.position = Vector2(60, 16)
	ui.add_child(coins_label)

	seed_label = _label("")
	seed_label.position = Vector2(16, 62)
	ui.add_child(seed_label)

	var shop_btn := _button("Магазин", 64)
	shop_btn.position = Vector2(348, 14)
	shop_btn.size = Vector2(176, 64)
	shop_btn.pressed.connect(_set_shop.bind(true))
	ui.add_child(shop_btn)

	# Подсказка, всплывающая надпись
	toast_label = _label("", 16)
	toast_label.position = Vector2(0, 108)
	toast_label.size = Vector2(540, 24)
	toast_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	toast_label.add_theme_color_override("font_outline_color", Color(0.05, 0.03, 0.02))
	toast_label.add_theme_constant_override("outline_size", 8)
	toast_label.modulate.a = 0.0
	toast_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(toast_label)

	# Джойстик и кнопка действия рисуются в одном слое
	controls = Control.new()
	controls.set_anchors_preset(Control.PRESET_FULL_RECT)
	controls.mouse_filter = Control.MOUSE_FILTER_IGNORE
	controls.draw.connect(_draw_controls)
	ui.add_child(controls)

	_build_shop(ui)


func _build_shop(ui: Control) -> void:
	shop = Control.new()
	shop.set_anchors_preset(Control.PRESET_FULL_RECT)
	shop.visible = false
	ui.add_child(shop)

	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	shop.add_child(dim)       # ловит нажатия, чтобы они не попали в игру

	var panel := PanelContainer.new()
	panel.position = Vector2(20, 110)
	panel.size = Vector2(500, 720)
	shop.add_child(panel)

	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 14)
	panel.add_child(box)

	var title := _label("МАГАЗИН", 24, Color(1, 0.85, 0.3))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title)

	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	box.add_child(scroll)

	shop_list = VBoxContainer.new()
	shop_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	shop_list.add_theme_constant_override("separation", 12)
	scroll.add_child(shop_list)

	var close := _button("Закрыть", 72)
	close.pressed.connect(_set_shop.bind(false))
	box.add_child(close)


func _refresh_shop() -> void:
	for c in shop_list.get_children():
		c.queue_free()
	shop_list.add_child(_label("Монеты: %d" % coins, 16, Color(1, 0.85, 0.3)))
	for i in MUSHROOMS.size():
		var m: Dictionary = MUSHROOMS[i]
		var info := _label("%s\nРост %d сек, цена %d" % [m["name"], int(m["grow"]), m["price"]])
		info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		shop_list.add_child(info)
		var b: Button
		if unlocked[i]:
			b = _button("Выбран" if i == selected else "Сажать этот", 64)
			b.disabled = i == selected
		else:
			b = _button("Открыть за %d" % m["unlock"], 64)
			b.disabled = coins < m["unlock"]
		b.pressed.connect(_on_select_pressed.bind(i))
		shop_list.add_child(b)
	var dig_info := _label("Копать глубже\n+2 грядки (сейчас %d из %d)" % [plot_count, MAX_PLOTS])
	dig_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	shop_list.add_child(dig_info)
	var dig := _button("Это максимум" if plot_count >= MAX_PLOTS else "Копать за %d" % _dig_cost(), 64)
	dig.disabled = plot_count >= MAX_PLOTS or coins < _dig_cost()
	dig.pressed.connect(_on_dig_pressed)
	shop_list.add_child(dig)


func _refresh_all() -> void:
	coins_label.text = str(coins)
	seed_label.text = MUSHROOMS[selected]["name"]     # что сажаем (цвет = цвет гриба)
	seed_label.add_theme_color_override("font_color", MUSHROOMS[selected]["color"])
	if shop.visible:
		_refresh_shop()
	_update_plots()


func _update_plots() -> void:
	var now := _now()
	for i in MAX_PLOTS:
		var n: Dictionary = plot_nodes[i]
		var open := i < plot_count
		n["bed"].visible = open
		n["rock"].visible = not open
		var shroom: Sprite2D = n["shroom"]
		var p: Dictionary = plots[i]
		plot_state[i] = 0
		if not open or p["type"] == -1:
			shroom.visible = false
			continue
		var m: Dictionary = MUSHROOMS[p["type"]]
		var progress: float = (now - p["planted_at"]) / m["grow"]
		var stage := 2 if progress >= 1.0 else (1 if progress >= 0.4 else 0)
		shroom.texture = shroom_tex[p["type"]][stage]
		shroom.visible = true
		plot_state[i] = 1 if stage == 2 else 0


func _toast(text: String) -> void:
	toast_label.text = text
	toast_label.modulate.a = 1.0
	if toast_tween:
		toast_tween.kill()
	toast_tween = create_tween()
	toast_tween.tween_interval(1.2)
	toast_tween.tween_property(toast_label, "modulate:a", 0.0, 0.5)


# ---------- Рисование джойстика и кнопки ----------

func _pixel_disc(c: Vector2, r: float, col: Color) -> void:
	# Круг из квадратиков 8x8, чтобы выглядел пиксельным.
	var step := 8.0
	var y := -r
	while y < r:
		var half := floorf(sqrt(maxf(r * r - (y + step / 2.0) * (y + step / 2.0), 0.0)) / step) * step
		controls.draw_rect(Rect2(c.x - half, c.y + y, half * 2.0, step), col)
		y += step


func _draw_controls() -> void:
	if shop.visible:
		return
	_pixel_disc(JOY_CENTER, JOY_RADIUS + 8, Color(0, 0, 0, 0.25))
	_pixel_disc(JOY_CENTER, JOY_RADIUS, Color(1, 1, 1, 0.12))
	_pixel_disc(JOY_CENTER + joy_vec * (JOY_RADIUS - 24), 32, Color(1, 0.9, 0.7, 0.55))

	var ready := target >= 0
	var pressed := act_id != NO_ID
	_pixel_disc(ACT_CENTER, ACT_RADIUS + 8, Color(0, 0, 0, 0.25))
	var col := Color(0.4, 0.8, 0.3, 0.55) if ready else Color(1, 1, 1, 0.12)
	if pressed:
		col = col.lightened(0.3)
	_pixel_disc(ACT_CENTER, ACT_RADIUS, col)
	var label := "Действие"
	if ready:
		var p: Dictionary = plots[target]
		if p["type"] == -1:
			label = "Посадить"
		elif _is_ripe(p):
			label = "Собрать"
		else:
			label = "Растёт"
	controls.draw_string(font, ACT_CENTER + Vector2(-ACT_RADIUS, 6), label,
			HORIZONTAL_ALIGNMENT_CENTER, ACT_RADIUS * 2, 16,
			Color(1, 1, 1, 1.0 if ready else 0.5))


# ---------- Вспомогательное ----------

func _now() -> float:
	return Time.get_unix_time_from_system()


func _is_ripe(p: Dictionary) -> bool:
	if p["type"] == -1:
		return false
	return _now() - p["planted_at"] >= MUSHROOMS[p["type"]]["grow"]


func _dig_cost() -> int:
	return 50 * (((plot_count - START_PLOTS) >> 1) + 1)


# ---------- Сохранение ----------
# Время посадки хранится как реальное время, поэтому грибы
# продолжают расти, даже когда игра закрыта.

func _save_game() -> void:
	var data := {
		"coins": coins,
		"unlocked": unlocked,
		"selected": selected,
		"plot_count": plot_count,
		"plots": plots,
	}
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(data))


func _load_game() -> void:
	plots = []
	if FileAccess.file_exists(SAVE_PATH):
		var data = JSON.parse_string(FileAccess.get_file_as_string(SAVE_PATH))
		if typeof(data) == TYPE_DICTIONARY:
			coins = int(data.get("coins", 0))
			selected = clampi(int(data.get("selected", 0)), 0, MUSHROOMS.size() - 1)
			plot_count = clampi(int(data.get("plot_count", START_PLOTS)), START_PLOTS, MAX_PLOTS)
			var u = data.get("unlocked", [])
			for i in unlocked.size():
				if i < u.size():
					unlocked[i] = bool(u[i])
			for p in data.get("plots", []):
				plots.append({
					"type": int(p.get("type", -1)),
					"planted_at": float(p.get("planted_at", 0.0)),
				})
	while plots.size() < MAX_PLOTS:
		plots.append({"type": -1, "planted_at": 0.0})


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST or what == NOTIFICATION_APPLICATION_PAUSED:
		_save_game()
