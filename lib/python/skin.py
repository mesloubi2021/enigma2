from glob import glob
from os.path import dirname, isfile, join as pathjoin, splitext
from os import listdir, unlink
from xml.etree.ElementTree import Element, ElementTree, fromstring

from enigma import BT_ALPHABLEND, BT_ALPHATEST, BT_HALIGN_CENTER, BT_HALIGN_LEFT, BT_HALIGN_RIGHT, BT_KEEP_ASPECT_RATIO, BT_SCALE, BT_VALIGN_BOTTOM, BT_VALIGN_CENTER, BT_VALIGN_TOP, addFont, eLabel, eListbox, ePixmap, ePoint, eRect, eRectangle, eSize, eSlider, eSubtitleWidget, eWidget, eWindow, eWindowStyleManager, eWindowStyleSkinned, getDesktop, gFont, getFontFaces, gMainDC, gRGB

from Components.config import ConfigSubsection, ConfigText, config
from Components.SystemInfo import BoxInfo
from Components.Sources.Source import ObsoleteSource
from Tools.Directories import SCOPE_LCDSKIN, SCOPE_GUISKIN, SCOPE_FONTS, SCOPE_SKINS, pathExists, resolveFilename, fileReadXML
from Tools.Import import my_import
from Tools.LoadPixmap import LoadPixmap

MODULE_NAME = __name__.split(".")[-1].capitalize()

DEFAULT_SKIN = "MetrixHD/skin.xml"
EMERGENCY_SKIN = "skin_default/skin.xml"
EMERGENCY_NAME = "Default OE-A"
DEFAULT_DISPLAY_SKIN = "skin_display_grautec.xml" if BoxInfo.getItem("grautec") else "skin_display.xml"
USER_SKIN = "skin_user.xml"
USER_SKIN_TEMPLATE = "skin_user_%s.xml"
SUBTITLE_SKIN = "skin_subtitles.xml"

GUI_SKIN_ID = 0  # Main frame-buffer.
DISPLAY_SKIN_ID = 2 if BoxInfo.getItem("model").startswith("dm") else 1  # Front panel / display / LCD.

domScreens = {}  # Dictionary of skin based screens.
colors = {  # Dictionary of skin color names.
	"key_back": gRGB(0x00313131),
	"key_blue": gRGB(0x0018188B),
	"key_green": gRGB(0x001F771F),
	"key_red": gRGB(0x009F1313),
	"key_text": gRGB(0x00FFFFFF),
	"key_yellow": gRGB(0x00A08500)
}
fonts = {  # Dictionary of predefined and skin defined font aliases.
	"Body": ("Regular", 18, 22, 16),
	"ChoiceList": ("Regular", 20, 24, 18)
}
menus = {}  # Dictionary of images associated with menu entries.
parameters = {}  # Dictionary of skin parameters used to modify code behavior.
setups = {}  # Dictionary of images associated with setup menus.
switchPixmap = {}  # Dictionary of switch images.
windowStyles = {}  # Dictionary of window styles for each screen ID.
resolutions = {}  # Dictionary of screen resolutions for each screen ID.
scrollLabelStyle = {}  # Dictionary of scrollLabel widget defaults.
constantWidgets = {}
layouts = {}
variables = {}
isVTISkin = False  # Temporary flag to suppress errors in OpenATV.

config.skin = ConfigSubsection()
skin = resolveFilename(SCOPE_SKINS, DEFAULT_SKIN)
if not isfile(skin):
	print(f"[Skin] Error: Default skin '{skin}' is not readable or is not a file!  Using emergency skin.")
	DEFAULT_SKIN = EMERGENCY_SKIN
config.skin.primary_skin = ConfigText(default=DEFAULT_SKIN)
config.skin.display_skin = ConfigText(default=DEFAULT_DISPLAY_SKIN)

currentPrimarySkin = None
currentDisplaySkin = None
callbacks = []
runCallbacks = False


# Skins are loaded in order of priority.  Skin with highest priority is
# loaded last.  This is usually the user-specified skin.  In this way
# any duplicated screens will be replaced by a screen of the same name
# with a higher priority.
#
# GUI skins are saved in the settings file as the path relative to
# SCOPE_SKINS.  The full path is NOT saved.  E.g. "MySkin/skin.xml"
#
# Display skins are saved in the settings file as the path relative to
# SCOPE_LCDSKIN.  The full path is NOT saved.
# E.g. "MySkin/skin_display.xml"
#
def InitSkins():
	global currentPrimarySkin, currentDisplaySkin, resolutions
	# #################################################################################################
	if isfile("/etc/.restore_skins"):
		unlink("/etc/.restore_skins")
		lastPath = ""
		for skin in sorted(glob("/usr/lib/enigma2/python/Plugins/Extensions/*/ActivateSkinSettings.py*")):
			try:
				print(f"[Skin] RESTORE_SKIN: Restore skin from '{skin}'...")
				skinPath, skinExt = splitext(skin)
				if skinPath == lastPath or skinExt not in (".py", ".pyc", ".pyo"):
					print("[Skin] RESTORE_SKIN: Skip!")
					continue
				lastPath = skinPath
				if getattr(__import__(skin.replace("/usr/lib/enigma2/python/", "").replace(skinExt, "").replace("/", "."), fromlist=["ActivateSkinSettings"]), "ActivateSkinSettings")().WriteSkin(True):
					print("[Skin] RESTORE_SKIN: Failed!")
				else:
					print("[Skin] RESTORE_SKIN: Done!")
			except Exception as err:
				print(f"[Skin] RESTORE_SKIN: Error occurred!  ({err})")
	# #################################################################################################
	runCallbacks = False
	# Add the emergency skin.  This skin should provide enough functionality
	# to enable basic GUI functions to work.
	loadSkin(EMERGENCY_SKIN, scope=SCOPE_GUISKIN, desktop=getDesktop(GUI_SKIN_ID), screenID=GUI_SKIN_ID)
	# Add the subtitle skin.
	loadSkin(SUBTITLE_SKIN, scope=SCOPE_GUISKIN, desktop=getDesktop(GUI_SKIN_ID), screenID=GUI_SKIN_ID)
	# Add the main GUI skin.
	result = []
	for skin, name in [(config.skin.primary_skin.value, "current"), (DEFAULT_SKIN, "default")]:
		if skin in result:  # Don't try to add a skin that has already failed.
			continue
		config.skin.primary_skin.value = skin
		if loadSkin(config.skin.primary_skin.value, scope=SCOPE_GUISKIN, desktop=getDesktop(GUI_SKIN_ID), screenID=GUI_SKIN_ID):
			currentPrimarySkin = config.skin.primary_skin.value
			break
		print(f"[Skin] Error: Adding {name} GUI skin '{config.skin.primary_skin.value}' has failed!")
		result.append(skin)
	# Add the front panel / display / lcd skin.
	result = []
	for skin, name in [(config.skin.display_skin.value, "current"), (DEFAULT_DISPLAY_SKIN, "default")]:
		if skin in result:  # Don't try to add a skin that has already failed.
			continue
		config.skin.display_skin.value = skin
		if loadSkin(config.skin.display_skin.value, scope=SCOPE_LCDSKIN, desktop=getDesktop(DISPLAY_SKIN_ID), screenID=DISPLAY_SKIN_ID):
			currentDisplaySkin = config.skin.display_skin.value
			break
		print(f"[Skin] Error: Adding {name} display skin '{config.skin.display_skin.value}' has failed!")
		result.append(skin)
	# Add the activated optional skin parts.
	if currentPrimarySkin is not None:
		partsDir = resolveFilename(SCOPE_GUISKIN, pathjoin(dirname(currentPrimarySkin), "mySkin", ""))
		if pathExists(partsDir) and currentPrimarySkin != DEFAULT_SKIN:
			for file in sorted(listdir(partsDir)):
				if file.startswith("skin_") and file.endswith(".xml"):
					partsFile = pathjoin(partsDir, file)
					if not loadSkin(partsFile, scope=SCOPE_GUISKIN, desktop=getDesktop(GUI_SKIN_ID), screenID=GUI_SKIN_ID):
						print(f"[Skin] Error: Failed to load modular skin file '{partsFile}'!")
	# Add an optional skin related user skin "user_skin_<SkinName>.xml".  If there is
	# not a skin related user skin then try to add am optional generic user skin.
	result = None
	if isfile(resolveFilename(SCOPE_SKINS, config.skin.primary_skin.value)):
		name = USER_SKIN_TEMPLATE % dirname(config.skin.primary_skin.value)
		if isfile(resolveFilename(SCOPE_GUISKIN, name)):
			result = loadSkin(name, scope=SCOPE_GUISKIN, desktop=getDesktop(GUI_SKIN_ID), screenID=GUI_SKIN_ID)
	if result is None:
		loadSkin(USER_SKIN, scope=SCOPE_GUISKIN, desktop=getDesktop(GUI_SKIN_ID), screenID=GUI_SKIN_ID)
	resolution = resolutions.get(GUI_SKIN_ID, (0, 0, 0))
	if resolution[0] and resolution[1]:
		gMainDC.getInstance().setResolution(resolution[0], resolution[1])
		getDesktop(GUI_SKIN_ID).resize(eSize(resolution[0], resolution[1]))
	runCallbacks = True


# Method to load a skin XML file into the skin data structures.
#
def loadSkin(filename, scope=SCOPE_SKINS, desktop=getDesktop(GUI_SKIN_ID), screenID=GUI_SKIN_ID):
	global windowStyles, resolutions
	filename = resolveFilename(scope, filename)
	print(f"[Skin] Loading skin file '{filename}'.")
	domSkin = fileReadXML(filename, source=MODULE_NAME)
	if domSkin:
		# For loadSingleSkinData colors, bordersets etc. are applied one after
		# the other in order of ascending priority.
		loadSingleSkinData(desktop, screenID, domSkin, filename, scope=scope)
		resolution = resolutions.get(screenID, (0, 0, 0))
		print(f"[Skin] Skin resolution is {resolution[0]}x{resolution[1]} and color depth is {resolution[2]} bits.")
		for element in domSkin:
			if element.tag == "screen":  # Process all screen elements.
				name = element.attrib.get("name")
				if name:  # Without a name, it's useless!
					scrnID = element.attrib.get("id")
					if scrnID is None or scrnID == screenID:  # If there is a screen ID is it for this display.
						res = element.attrib.get("resolution", f"{resolution[0]},{resolution[1]}")
						if res != "0,0":
							element.attrib["resolution"] = res
						if config.crash.debugScreens.value:
							res = [parseInteger(x.strip()) for x in res.split(",")]
							msg = f", resolution {res[0]}x{res[1]}," if len(res) == 2 and res[0] and res[1] else ""
							print(f"[Skin] Loading screen '{name}'{msg} from '{filename}'.  (scope={scope})")
						domScreens[name] = (element, f"{dirname(filename)}/")
			elif element.tag == "windowstyle":  # Process the windowstyle element.
				scrnID = element.attrib.get("id")
				if scrnID is not None:  # Without an scrnID, it is useless!
					scrnID = parseInteger(scrnID)
					domStyle = ElementTree(Element("skin"))
					domStyle.getroot().append(element)
					windowStyles[scrnID] = (desktop, screenID, domStyle.getroot(), filename, scope)
					if config.crash.debugScreens.value:
						print(f"[Skin] This skin has a windowstyle for screen ID='{scrnID}'.")
			# Element is not a screen or windowstyle element so no need for it any longer.
		print(f"[Skin] Loading skin file '{filename}' complete.")
		if runCallbacks:
			for method in callbacks:
				if method:
					method()
		return True
	return False


def reloadSkins():
	global colors, domScreens, fonts, menus, parameters, setups, switchPixmap
	domScreens.clear()
	colors.clear()
	colors = {
		"key_back": gRGB(0x00313131),
		"key_blue": gRGB(0x0018188B),
		"key_green": gRGB(0x001F771F),
		"key_red": gRGB(0x009F1313),
		"key_text": gRGB(0x00FFFFFF),
		"key_yellow": gRGB(0x00A08500)
	}
	fonts.clear()
	fonts = {
		"Body": ("Regular", 18, 22, 16),
		"ChoiceList": ("Regular", 20, 24, 18)
	}
	menus.clear()
	parameters.clear()
	setups.clear()
	switchPixmap.clear()
	InitSkins()


def addCallback(callback):
	global callbacks
	if callback not in callbacks:
		callbacks.append(callback)


def removeCallback(callback):
	global callbacks
	if callback in callbacks:
		callbacks.remove(callback)


def getParentSize(object, desktop):
	if object:
		parent = object.getParent()
		# For some widgets (e.g. ScrollLabel) the skin attributes are applied to a
		# child widget, instead of to the widget itself.  In that case, the parent
		# we have here is not the real parent, but it is the main widget.  We have
		# to go one level higher to get the actual parent.  We can detect this
		# because the 'parent' will not have a size yet.  (The main widget's size
		# will be calculated internally, as soon as the child widget has parsed the
		# skin attributes.)
		if parent and parent.size().isEmpty():
			parent = parent.getParent()
		if parent:
			return parent.size()
		elif desktop:
			return desktop.size()  # Widget has no parent, use desktop size instead for relative coordinates.
	return eSize()


def skinError(errorMessage):
	print(f"[Skin] Error: {errorMessage}!")


def attribDeprecationWarning(attribute, replacement):
	print(f"[Skin] Warning: Attribute '{attribute}' has been deprecated, use '{replacement}' instead!")


def parseOptions(options, attribute, value, default):
	if options and isinstance(options, dict):
		if value in options.keys():
			value = options[value]
		else:
			optionList = "', '".join(options.keys())
			skinError(f"The '{attribute}' value '{value}' is invalid, acceptable options are '{optionList}'")
			value = default
	else:
		skinError("The '%s' parser is not correctly initialized")
		value = default
	return value


def parseAlphaTest(value):
	options = {
		"on": BT_ALPHATEST,
		"off": 0,
		"blend": BT_ALPHABLEND
	}
	return parseOptions(options, "alphaTest", value, 0)


def parseAnimationMode(value):
	options = {
		"disable": 0x00,
		"off": 0x00,
		"offshow": 0x10,
		"offhide": 0x01,
		"onshow": 0x01,
		"onhide": 0x10,
		"disable_onshow": 0x10,
		"disable_onhide": 0x01
	}
	return parseOptions(options, "animationMode", value, 0x00)


def parseBoolean(attribute, value):
	return value.lower() in ("1", attribute, "enabled", "on", "true", "yes")


def parseColor(value, default=0x00FFFFFF):
	if value[0] == "#":
		try:
			value = gRGB(int(value[1:], 0x10))
		except ValueError:
			skinError(f"The color code '{value}' must be #aarrggbb, using #00FFFFFF (White)")
			value = gRGB(default)
	elif value in colors:
		value = colors[value]
	else:
		skinError(f"The color '{value}' must be #aarrggbb or valid named color, using #00FFFFFF (White)")
		value = gRGB(default)
	return value


# Convert a coordinate string into a number.  Used to convert object position and
# size attributes into a number.
#    s is the input string.
#    e is the the parent object size to do relative calculations on parent
#    size is the size of the object size (e.g. width or height)
#    font is a font object to calculate relative to font sizes
# Note some constructs for speeding up simple cases that are very common.
#
# Can do things like:  10+center-10w+4%
# To center the widget on the parent widget,
#    but move forward 10 pixels and 4% of parent width
#    and 10 character widths backward
# Multiplication, division and subexpressions are also allowed: 3*(e-c/2)
#
# Usage:  center : Center the object on parent based on parent size and object size.
#         e      : Take the parent size/width.
#         c      : Take the center point of parent size/width.
#         %      : Take given percentage of parent size/width.
#         w      : Multiply by current font width. (Only to be used in elements where the font attribute is available, i.e. not "None")
#         h      : Multiply by current font height. (Only to be used in elements where the font attribute is available, i.e. not "None")
#         f      : Replace with getSkinFactor().
#
def parseCoordinate(value, parent, size=0, font=None, scale=(1, 1)):
	def scaleNumbers(coordinate, scale):
		inNumber = False
		chars = []
		digits = []
		for char in list(f"{coordinate} "):
			if char.isdigit():
				inNumber = True
				digits.append(char)
			elif inNumber:
				inNumber = False
				chars.append(str(int(int("".join(digits)) * scale[0] / scale[1])))
				digits = []
				chars.append(char)
			else:
				chars.append(char)
		return "".join(chars).strip()

	value = value.strip()
	try:
		result = int(int(value) * scale[0] / scale[1])  # For speed try a simple number first.
	except ValueError:
		if value == "center":  # For speed as this can be common case.
			return max(int((parent - size) // 2) if size else 0, 0)
		elif value == "*":
			return None
		if font is None:
			font = "Body"
			if "w" in value or "h" in value:
				print(f"[Skin] Warning: Coordinate 'w' and/or 'h' used but font is None, '{font}' font ('{fonts[font][0]}', width={fonts[font][3]}, height={fonts[font][2]}) assumed!")
		val = scaleNumbers(value, scale)
		if "center" in val:
			val = val.replace("center", str((parent - size) / 2.0))
		if "e" in val:
			val = val.replace("e", str(parent))
		if "c" in val:
			val = val.replace("c", str(parent / 2.0))
		if "%" in val:
			val = val.replace("%", f"*{parent / 100.0}")
		if "w" in val:
			val = val.replace("w", f"*{fonts[font][3]}")
		if "h" in val:
			val = val.replace("h", f"*{fonts[font][2]}")
		if "f" in val:
			val = val.replace("f", f"{getSkinFactor()}")
		try:
			result = int(val)  # For speed try a simple number first.
		except ValueError:
			try:
				result = int(eval(val))
			except Exception as err:
				print(f"[Skin] Error ({type(err).__name__} - {err}): Coordinate '{value}', calculated to '{val}', can't be evaluated!")
				result = 0
	# print(f"[Skin] parseCoordinate DEBUG: value='{value}', parent='{parent}', size={size}, font='{font}', scale='{scale}', result='{result}'.")
	return 0 if result < 0 else result


def parseFont(value, scale=((1, 1), (1, 1))):
	if ";" in value:
		(name, size) = value.split(";")
		try:
			size = int(size)
		except ValueError:
			try:
				val = size.replace("f", f"{getSkinFactor()}")
				size = int(eval(val))
			except Exception as err:
				print(f"[Skin] Error ({type(err).__name__} - {err}): Font size in '{value}', evaluated to '{val}', can't be processed!")
				size = None
	else:
		name = value
		size = None
	try:
		font = fonts[name]
		name = font[0]
		size = font[1] if size is None else size
	except KeyError:
		if name not in getFontFaces():
			font = fonts["Body"]
			print(f"[Skin] Error: Font '{name}' (in '{value}') is not defined!  Using 'Body' font ('{font[0]}') instead.")
			name = font[0]
			size = font[1] if size is None else size
	# print(f"[Skin] DEBUG: Scale font {size} -> {int(size * scale[1][0] / scale[1][1])}.")
	return gFont(name, int(size * scale[1][0] / scale[1][1]))


def parseGradient(value):
	def validColor(value):
		if value[0] == "#" and 7 < len(value) < 10:
			isColor = True
		elif value in colors:
			isColor = True
		else:
			isColor = False
		return isColor

	data = [x.strip() for x in value.split(",")]
	gradientColors = [gRGB(0x00000000), gRGB(0x00FFFFFF), gRGB(0x00FFFFFF)]  # Start color, center color, end color.
	for index, color in enumerate(data):
		if not validColor(color) or index > 2:
			break
		gradientColors[index] = parseColor(color)
	if index == 2:
		gradientColors[2] = gradientColors[1]
	argCount = len(data) - index - 1
	if index > 1 and argCount:
		options = {
			"horizontal": eWidget.GRADIENT_HORIZONTAL,
			"vertical": eWidget.GRADIENT_VERTICAL,
		}
		direction = parseOptions(options, "gradient", data[index], eWidget.GRADIENT_VERTICAL)
		alphaBlend = 1 if argCount > 1 and parseBoolean("alphablend", data[index + 1]) else 0
	else:
		skinError(f"The gradient '{value}' must be 'startColor[,centerColor],endColor,direction[,alphaBlend]', using '#00000000,#00FFFFFF,vertical' (Black,White,vertical)")
		direction = eWidget.GRADIENT_VERTICAL
		alphaBlend = 0
	return (gradientColors[0], gradientColors[1], gradientColors[2], direction, alphaBlend)


def parseHorizontalAlignment(value):
	options = {
		"left": 0,
		"center": 1,
		"right": 2,
		"block": 3
	}
	return parseOptions(options, "horizontalAlignment", value, 0)


def parseInteger(value, default=0):
	try:
		value = int(value)
	except (TypeError, ValueError):
		skinError(f"The value '{value}' is not a valid integer")
		value = default
	return value


def parseItemAlignment(value):
	options = {
		"default": eListbox.itemAlignLeftTop,
		"center": eListbox.itemAlignCenterMiddle,
		"justify": eListbox.itemAlignJustifyFull,
		"leftTop": eListbox.itemAlignLeftTop,
		"leftMiddle": eListbox.itemAlignLeftMiddle,
		"leftBottom": eListbox.itemAlignLeftBottom,
		"rightTop": eListbox.itemAlignRightTop,
		"rightMiddle": eListbox.itemAlignRightMiddle,
		"rightBottom": eListbox.itemAlignRightBottom,
		"centerTop": eListbox.itemAlignCenterTop,
		"centerMiddle": eListbox.itemAlignCenterMiddle,
		"centerBottom": eListbox.itemAlignCenterBottom,
		"justifyTop": eListbox.itemAlignJustifyTop,
		"justifyMiddle": eListbox.itemAlignJustifyMiddle,
		"justifyBottom": eListbox.itemAlignJustifyBottom,
		"justifyLeft": eListbox.itemAlignJustifyLeft,
		"justifyRight": eListbox.itemAlignJustifyRight
	}
	return parseOptions(options, "itemAlignment", value, eListbox.itemAlignLeftTop)


def parseScrollbarLength(value, default):
	if value and value.isdigit():
		return int(value)
	options = {
		"full": 0,
		"auto": -1
	}
	return options.get(value, default)


def parseListOrientation(value):
	options = {
		"vertical": 0b01,
		"horizontal": 0b10,
		"grid": 0b11
	}
	return options.get(value, 0b01)


def parseOrientation(value):
	options = {
		"orHorizontal": 0x00,
		"orLeftToRight": 0x00,
		"orRightToLeft": 0x01,
		"orVertical": 0x10,
		"orTopToBottom": 0x10,
		"orBottomToTop": 0x11
	}
	value = parseOptions(options, "orientation", value, 0x00)
	return (value & 0x10, value & 0x01)  # (orHorizontal / orVertical, not swapped / swapped)


# Convert a parameter string into a value based on string triggers.  The type
# and value returned is based on the trigger.
#
# Usage:  *string   : The paramater is a string with the "*" is removed (Type: String).
#         #aarrggbb : The parameter is a HEX color string (Type: Integer).
#         0xABCD    : The parameter is a HEX integer (Type: Integer).
#         5.3       : The parameter is a floating point number (Type: Float).
#         red       : The parameter is a named color (Type: Integer).
#         font;zize : The parameter is a font name with a font size (Type: List[Font, Size]).
#         123       : The parameter is an integer (Type: Integer).
#
def parseParameter(value):
	"""This function is responsible for parsing parameters in the skin, it can parse integers, floats, hex colors, hex integers, named colors, fonts and strings."""
	if value[0] == "*":  # String.
		return value[1:]
	elif value[0] == "#":  # HEX Color.
		return int(value[1:], 16)
	elif value[:2] == "0x":  # HEX Integer.
		return int(value, 16)
	elif "." in value:  # Float number.
		return float(value)
	elif value in colors:  # Named color.
		return colors[value].argb()
	elif value.find(";") != -1:  # Font.
		(font, size) = (x.strip() for x in value.split(";", 1))
		return [font, int(size)]
	else:  # Integer.
		return int(value)


def parsePixmap(path, desktop):
	option = path.find("#")
	if option != -1:
		path = path[:option]
	if isfile(path):
		pixmap = LoadPixmap(path, desktop=desktop)
		if pixmap is None:
			skinError(f"Pixmap file '{path}' could not be loaded")
	else:
		skinError(f"Pixmap '{path}' is not found or is not a file")
		pixmap = None
	return pixmap


def parsePosition(value, scale, object=None, desktop=None, size=None):
	return ePoint(*parseValuePair(value, scale, object, desktop, size))


def parseRadius(value):
	data = [x.strip() for x in value.split(";")]
	if len(data) == 2:
		edges = [x.strip() for x in data[1].split(",")]
		edgesMask = {
			"topLeft": eWidget.RADIUS_TOP_LEFT,
			"topRight": eWidget.RADIUS_TOP_RIGHT,
			"top": eWidget.RADIUS_TOP,
			"bottomLeft": eWidget.RADIUS_BOTTOM_LEFT,
			"bottomRight": eWidget.RADIUS_BOTTOM_RIGHT,
			"bottom": eWidget.RADIUS_BOTTOM,
			"left": eWidget.RADIUS_LEFT,
			"right": eWidget.RADIUS_RIGHT,
		}
		edgeValue = 0
		for edge in edges:
			edgeValue += edgesMask.get(edge, 0)
		return int(data[0]), edgeValue
	else:
		return int(data[0]), eWidget.RADIUS_ALL


def parseSize(value, scale, object=None, desktop=None):
	return eSize(*parseValuePair(value, scale, object, desktop))


def parseValuePair(value, scale, object=None, desktop=None, size=None):
	if value in variables:
		value = variables[value]
	(xValue, yValue) = value.split(",")  # These values will be stripped in parseCoordinate().
	parentsize = eSize()
	if object and ("c" in xValue or "c" in yValue or "e" in xValue or "e" in yValue or "%" in xValue or "%" in yValue):  # Need parent size for 'c', 'e' and '%'.
		parentsize = getParentSize(object, desktop)
	# x = xValue
	# y = yValue
	xValue = parseCoordinate(xValue, parentsize.width(), size and size.width() or 0, None, scale[0])
	yValue = parseCoordinate(yValue, parentsize.height(), size and size.height() or 0, None, scale[1])
	# print(f"[Skin] parseValuePair DEBUG: Scaled pair X {x} -> {xValue}, Y {y} -> {yValue}.")
	return (xValue, yValue)


def parseScale(value):
	options = {
		"none": 0,
		"0": 0,  # Legacy scale option.
		"scale": BT_SCALE,
		"1": BT_SCALE,  # Legacy scale option.
		"keepAspect": BT_SCALE | BT_KEEP_ASPECT_RATIO,
		"leftTop": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_LEFT | BT_VALIGN_TOP,
		"leftCenter": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_LEFT | BT_VALIGN_CENTER,
		"leftMiddle": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_LEFT | BT_VALIGN_CENTER,
		"leftBottom": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_LEFT | BT_VALIGN_BOTTOM,
		"centerTop": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_TOP,
		"middleTop": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_TOP,
		"centerScaled": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_CENTER,
		"middleScaled": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_CENTER,
		"centerBottom": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_BOTTOM,
		"middleBottom": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_BOTTOM,
		"rightTop": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_RIGHT | BT_VALIGN_TOP,
		"rightCenter": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_RIGHT | BT_VALIGN_CENTER,
		"rightMiddle": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_RIGHT | BT_VALIGN_CENTER,
		"rightBottom": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_RIGHT | BT_VALIGN_BOTTOM,
		#
		# Deprecated scaling names.
		"scaleKeepAspect": BT_SCALE | BT_KEEP_ASPECT_RATIO,
		"scaleLeftTop": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_LEFT | BT_VALIGN_TOP,
		"scaleLeftCenter": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_LEFT | BT_VALIGN_CENTER,
		"scaleLeftMiddle": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_LEFT | BT_VALIGN_CENTER,
		"scaleLeftBottom": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_LEFT | BT_VALIGN_BOTTOM,
		"scaleCenterTop": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_TOP,
		"scaleMiddleTop": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_TOP,
		"scaleCenter": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_CENTER,
		"scaleMiddle": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_CENTER,
		"scaleCenterBottom": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_BOTTOM,
		"scaleMiddleBottom": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_BOTTOM,
		"scaleRightTop": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_RIGHT | BT_VALIGN_TOP,
		"scaleRightCenter": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_RIGHT | BT_VALIGN_CENTER,
		"scaleRightMiddle": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_RIGHT | BT_VALIGN_CENTER,
		"scaleRightBottom": BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_RIGHT | BT_VALIGN_BOTTOM,
		#
		"moveLeftTop": BT_HALIGN_LEFT | BT_VALIGN_TOP,
		"moveLeftCenter": BT_HALIGN_LEFT | BT_VALIGN_CENTER,
		"moveLeftMiddle": BT_HALIGN_LEFT | BT_VALIGN_CENTER,
		"moveLeftBottom": BT_HALIGN_LEFT | BT_VALIGN_BOTTOM,
		"moveCenterTop": BT_HALIGN_CENTER | BT_VALIGN_TOP,
		"moveMiddleTop": BT_HALIGN_CENTER | BT_VALIGN_TOP,
		"moveCenter": BT_HALIGN_CENTER | BT_VALIGN_CENTER,
		"moveMiddle": BT_HALIGN_CENTER | BT_VALIGN_CENTER,
		"moveCenterBottom": BT_HALIGN_CENTER | BT_VALIGN_BOTTOM,
		"moveMiddleBottom": BT_HALIGN_CENTER | BT_VALIGN_BOTTOM,
		"moveRightTop": BT_HALIGN_RIGHT | BT_VALIGN_TOP,
		"moveRightCenter": BT_HALIGN_RIGHT | BT_VALIGN_CENTER,
		"moveRightMiddle": BT_HALIGN_RIGHT | BT_VALIGN_CENTER,
		"moveRightBottom": BT_HALIGN_RIGHT | BT_VALIGN_BOTTOM,
		#
		# For compatibility with DreamOS and VTi skins:
		"off": 0,  # Do not scale.
		"on": BT_SCALE | BT_KEEP_ASPECT_RATIO,  # Scale but keep aspect ratio.
		"aspect": BT_SCALE | BT_KEEP_ASPECT_RATIO,  # Scale but keep aspect ratio.
		"center": BT_HALIGN_CENTER | BT_VALIGN_CENTER,  # Do not scale but center on target.
		"width": BT_SCALE | BT_VALIGN_CENTER,  # Adjust the width to the target, the height can be too big or too small.
		"height": BT_SCALE | BT_HALIGN_CENTER,  # Adjust height to target, width can be too big or too small.
		"stretch": BT_SCALE,  # Adjust height and width to the target, aspect may break.
		"fill": BT_SCALE | BT_HALIGN_CENTER | BT_VALIGN_CENTER  # Scaled so large that the target is completely filled, may be too wide OR too high, "width" or "height" is only automatically selected depending on which side is "too small".
	}
	return parseOptions(options, "scale", value, 0)


def parseScrollbarMode(value):
	options = {
		"showOnDemand": eListbox.showOnDemand,
		"showAlways": eListbox.showAlways,
		"showNever": eListbox.showNever,
		"showLeft": eListbox.showLeftOnDemand,  # This value is deprecated to better allow option symmetry, use "showLeftOnDemand" instead.
		"showLeftOnDemand": eListbox.showLeftOnDemand,
		"showLeftAlways": eListbox.showLeftAlways,
		"showTopOnDemand": eListbox.showTopOnDemand,
		"showTopAlways": eListbox.showTopAlways
	}
	return parseOptions(options, "scrollbarMode", value, eListbox.showOnDemand)


def parseScrollbarScroll(value):
	options = {
		"byPage": 0,
		"byLine": 1
	}
	return parseOptions(options, "scrollbarScroll", value, 0)


def parsePadding(attribute, value):
	if value in variables:
		value = variables[value]
	padding = [parseInteger(x.strip()) for x in value.split(",")]
	count = len(padding)
	if count == 1:
		padding *= 4
	elif count == 2:
		padding *= 2
	elif count != 4:
		print(f"[Skin] Error: Attribute '{attribute}' with value '{value}' is invalid!  Attribute must have 1, 2 or 4 values.")
		padding = [0, 0, 0, 0]
	return padding


def parseVerticalAlignment(value):
	options = {
		"top": 0,
		"center": 1,
		"middle": 1,
		"bottom": 2
	}
	return parseOptions(options, "verticalAlignment", value, 1)


def parseWrap(value):
	options = {
		"noWrap": 0,
		"off": 0,
		"0": 0,
		"wrap": 1,
		"on": 1,
		"1": 1,
		"ellipsis": 2
	}
	return parseOptions(options, "wrap", value, 0)


def parseZoom(mode, zoomType):
	options = {
		"zoomContent": eListbox.zoomContentZoom,
		"moveContent": eListbox.zoomContentMove,
		"ignoreContent": eListbox.zoomContentOff
	}
	return parseOptions(options, zoomType, mode, eListbox.zoomContentZoom)


def collectAttributes(skinAttributes, node, context, skinPath=None, ignore=(), filenames=frozenset(("pixmap", "pointer", "seekPointer", "seek_pointer", "backgroundPixmap", "selectionPixmap", "sliderPixmap", "scrollbarBackgroundPixmap", "scrollbarForegroundPixmap", "scrollbarbackgroundPixmap", "scrollbarBackgroundPicture", "scrollbarSliderPicture"))):
	size = None
	pos = None
	font = None
	for attrib, value in node.items():  # Walk all attributes.
		if attrib not in ignore:
			newValue = value
			if attrib in filenames:
				# DEBUG: Why does a SCOPE_LCDSKIN image replace the GUI image?!?!?!
				pngFile = resolveFilename(SCOPE_GUISKIN, value, path_prefix=skinPath)
				if not isfile(pngFile) and isfile(resolveFilename(SCOPE_LCDSKIN, value, path_prefix=skinPath)):
					pngFile = resolveFilename(SCOPE_LCDSKIN, value, path_prefix=skinPath)
				newValue = pngFile
			# Bit of a hack this, really.  When a window has a flag (e.g. wfNoBorder)
			# it needs to be set at least before the size is set, in order for the
			# window dimensions to be calculated correctly in all situations.
			# If wfNoBorder is applied after the size has been set, the window will
			# fail to clear the title area.  Similar situation for a scrollbar in a
			# listbox; when the scrollbar setting is applied after the size, a scrollbar
			# will not be shown until the selection moves for the first time.
			if attrib == "size":
				size = newValue
			elif attrib == "position":
				pos = newValue
			elif attrib == "font":
				font = newValue
				skinAttributes.append((attrib, newValue))
			else:
				skinAttributes.append((attrib, newValue))
	if pos is not None:
		pos, size = context.parse(pos, size, font)
		skinAttributes.append(("position", pos))
	if size is not None:
		skinAttributes.append(("size", size))


class AttributeParser:
	def __init__(self, guiObject, desktop, scale=((1, 1), (1, 1))):
		self.guiObject = guiObject
		self.desktop = desktop
		self.scaleTuple = scale

	def applyAll(self, attributes):
		# attributes.sort(key=lambda x: {"pixmap": 1}.get(x[0], 0))  # For SVG pixmap scale required the size, so sort pixmap last.
		for attribute, value in attributes:
			self.applyOne(attribute, value)

	def applyOne(self, attribute, value):
		try:
			getattr(self, attribute)(value)
		except Exception as err:
			print(f"[Skin] Error: Attribute '{attribute}' with value '{value}' in object of type '{self.guiObject.__class__.__name__}' ({err})!")

	def applyHorizontalScale(self, value):
		return int(parseInteger(value) * self.scaleTuple[0][0] / self.scaleTuple[0][1])

	def applyVerticalScale(self, value):
		return int(parseInteger(value) * self.scaleTuple[1][0] / self.scaleTuple[1][1])

	def alphaTest(self, value):
		self.guiObject.setAlphatest(parseAlphaTest(value))

	def alphatest(self, value):  # This legacy definition uses an inconsistent name, use 'alphaTest' instead!
		self.alphaTest(value)
		# attribDeprecationWarning("alphatest", "alphaTest")

	def animationMode(self, value):
		self.guiObject.setAnimationMode(parseAnimationMode(value))

	def animationPaused(self, value):
		pass

	def backgroundColor(self, value):
		self.guiObject.setBackgroundColor(parseColor(value, 0x00000000))

	def backgroundColorSelected(self, value):
		self.guiObject.setBackgroundColorSelected(parseColor(value, 0x00000000))

	def backgroundCrypted(self, value):
		self.guiObject.setBackgroundColor(parseColor(value, 0x00000000))

	def backgroundEncrypted(self, value):
		self.guiObject.setBackgroundColor(parseColor(value, 0x00000000))

	def backgroundGradient(self, value):
		self.guiObject.setBackgroundGradient(*parseGradient(value))

	def backgroundGradientSelected(self, value):
		self.guiObject.setBackgroundGradientSelected(*parseGradient(value))

	def backgroundNotCrypted(self, value):
		self.guiObject.setBackgroundColor(parseColor(value, 0x00000000))

	def backgroundPixmap(self, value):
		self.guiObject.setBackgroundPixmap(parsePixmap(value, self.desktop))

	def borderColor(self, value):
		self.guiObject.setBorderColor(parseColor(value, 0x00FFFFFF))

	def borderWidth(self, value):
		self.guiObject.setBorderWidth(self.applyVerticalScale(value))

	def conditional(self, value):
		pass

	def cornerRadius(self, value):
		radius, edgeValue = parseRadius(value)
		self.guiObject.setCornerRadius(radius, edgeValue)

	def enableWrapAround(self, value):
		self.guiObject.setWrapAround(parseBoolean("enablewraparound", value))

	def entryFont(self, value):
		self.guiObject.setEntryFont(parseFont(value, self.scaleTuple))

	def excludes(self, value):
		pass

	def flags(self, value):
		if value in variables:
			value = variables[value]
		errors = []
		flags = [x.strip() for x in value.split(",")]
		for flag in flags:
			try:
				self.guiObject.setFlag(eWindow.__dict__[flag])
			except KeyError:
				errors.append(flag)
		if errors:
			errorList = "', '".join(errors)
			print(f"[Skin] Error: Attribute 'flags' with value '%s' has invalid element(s) '{errorList}'!")

	def font(self, value):
		self.guiObject.setFont(parseFont(value, self.scaleTuple))

	def foregroundColor(self, value):
		self.guiObject.setForegroundColor(parseColor(value, 0x00FFFFFF))

	def foregroundColorSelected(self, value):
		self.guiObject.setForegroundColorSelected(parseColor(value, 0x00FFFFFF))

	def foregroundCrypted(self, value):
		self.guiObject.setForegroundColor(parseColor(value, 0x00FFFFFF))

	def foregroundEncrypted(self, value):
		self.guiObject.setForegroundColor(parseColor(value, 0x00FFFFFF))

	def foregroundGradient(self, value):
		self.guiObject.setForegroundGradient(*parseGradient(value))

	def foregroundNotCrypted(self, value):
		self.guiObject.setForegroundColor(parseColor(value, 0x00FFFFFF))

	def hAlign(self, value):  # This typo catcher definition uses an inconsistent name, use 'horizontalAlignment' instead!
		self.horizontalAlignment(value)
		# attribDeprecationWarning("hAlign", "horizontalAlignment")

	def halign(self, value):  # This legacy definition uses an inconsistent name, use 'horizontalAlignment' instead!
		self.horizontalAlignment(value)
		# attribDeprecationWarning("halign", "horizontalAlignment")

	def horizontalAlignment(self, value):
		self.guiObject.setHAlign(parseHorizontalAlignment(value))

	def includes(self, value):  # Same as conditional.  Created to partner new "excludes" attribute.
		pass

	def itemAlignment(self, value):
		self.guiObject.setItemAlignment(parseItemAlignment(value))

	def itemCornerRadius(self, value):
		radius, edgeValue = parseRadius(value)
		self.guiObject.setItemCornerRadius(radius, edgeValue)

	def itemCornerRadiusMarked(self, value):
		radius, edgeValue = parseRadius(value)
		self.guiObject.setItemCornerRadiusMarked(radius, edgeValue)

	def itemCornerRadiusMarkedAndSelected(self, value):
		radius, edgeValue = parseRadius(value)
		self.guiObject.setItemCornerRadiusMarkedAndSelected(radius, edgeValue)

	def itemCornerRadiusSelected(self, value):
		radius, edgeValue = parseRadius(value)
		self.guiObject.setItemCornerRadiusSelected(radius, edgeValue)

	def itemGradient(self, value):
		self.guiObject.setItemGradient(*parseGradient(value))

	def itemGradientMarked(self, value):
		self.guiObject.setItemGradientMarked(*parseGradient(value))

	def itemGradientMarkedAndSelected(self, value):
		self.guiObject.setItemGradientMarkedAndSelected(*parseGradient(value))

	def itemGradientSelected(self, value):
		self.guiObject.setItemGradientSelected(*parseGradient(value))

	def itemHeight(self, value):
		# print(f"[Skin] DEBUG: Scale itemHeight {int(value)} -> {self.applyVerticalScale(value)}.")
		self.guiObject.setItemHeight(self.applyVerticalScale(value))

	def itemSpacing(self, value):
		if len(value.split(",")) == 1:  # These values will be stripped in parseCoordinate().
			value = f"{value},{value}"
		self.guiObject.setItemSpacing(parsePosition(value, self.scaleTuple, self.guiObject, self.desktop))

	def itemWidth(self, value):
		# print(f"[Skin] DEBUG: Scale itemWidth {int(value)} -> {self.applyHorizontalScale(value)}.")
		self.guiObject.setItemWidth(self.applyHorizontalScale(value))

	def listOrientation(self, value):  # Used by eListBox.
		self.guiObject.setOrientation(parseListOrientation(value))

	def noWrap(self, value):
		self.wrap("0" if parseBoolean("noWrap", value) else "1")
		# attribDeprecationWarning("noWrap", "wrap")

	def objectTypes(self, value):
		pass

	def orientation(self, value):  # Used by eSlider.
		self.guiObject.setOrientation(*parseOrientation(value))

	def OverScan(self, value):  # This legacy definition uses an inconsistent name, use 'overScan' instead!
		self.overScan(value)
		attribDeprecationWarning("OverScan", "overScan")

	def overScan(self, value):
		self.guiObject.setOverscan(value)

	def padding(self, value):
		leftPadding, topPadding, rightPadding, bottomPadding = parsePadding("padding", value)
		self.guiObject.setPadding(eRect(self.applyHorizontalScale(leftPadding), self.applyVerticalScale(topPadding), self.applyHorizontalScale(rightPadding), self.applyVerticalScale(bottomPadding)))

	def pixmap(self, value):
		self.guiObject.setPixmap(parsePixmap(value, self.desktop))

	def pointer(self, value):
		(name, pos) = (x.strip() for x in value.split(":", 1))
		ptr = parsePixmap(name, self.desktop)
		pos = parsePosition(pos, self.scaleTuple)
		self.guiObject.setPointer(0, ptr, pos)

	def position(self, value):
		self.guiObject.move(ePoint(*value) if isinstance(value, tuple) else parsePosition(value, self.scaleTuple, self.guiObject, self.desktop, self.guiObject.csize()))

	def resolution(self, value):
		pass

	def scale(self, value):
		self.guiObject.setPixmapScale(parseScale(value))

	def scaleFlags(self, value):  # This is a temporary patch until the code and skins using this attribute is updated.
		self.scale(value)

	def scrollbarBackgroundColor(self, value):
		self.guiObject.setScrollbarBackgroundColor(parseColor(value, 0x00000000))

	def scrollbarBackgroundGradient(self, value):
		self.guiObject.setScrollbarBackgroundGradient(*parseGradient(value))

	def scrollbarBackgroundPicture(self, value):  # For compatibility same as 'scrollbarBackgroundPixmap', use 'scrollbarBackgroundPixmap' instead.
		self.scrollbarBackgroundPixmap(value)
		attribDeprecationWarning("scrollbarBackgroundPicture", "scrollbarBackgroundPixmap")

	def scrollbarBackgroundPixmap(self, value):
		self.guiObject.setScrollbarBackgroundPixmap(parsePixmap(value, self.desktop))

	def scrollbarbackgroundPixmap(self, value):  # This legacy definition uses an inconsistent name, use'scrollbarBackgroundPixmap' instead!
		self.scrollbarBackgroundPixmap(value)
		attribDeprecationWarning("scrollbarbackgroundPixmap", "scrollbarBackgroundPixmap")

	def scrollbarBorderColor(self, value):
		self.guiObject.setScrollbarBorderColor(parseColor(value, 0x00FFFFFF))

	def scrollbarBorderWidth(self, value):
		self.guiObject.setScrollbarBorderWidth(self.applyHorizontalScale(value))

	def scrollbarForegroundColor(self, value):
		self.guiObject.setScrollbarForegroundColor(parseColor(value, 0x00FFFFFF))

	def scrollbarForegroundGradient(self, value):
		self.guiObject.setScrollbarForegroundGradient(*parseGradient(value))

	def scrollbarForegroundPixmap(self, value):
		self.guiObject.setScrollbarForegroundPixmap(parsePixmap(value, self.desktop))

	def scrollbarLength(self, value):
		self.guiObject.setScrollbarLength(parseScrollbarLength(value, 0))

	def scrollbarMode(self, value):
		self.guiObject.setScrollbarMode(parseScrollbarMode(value))

	def scrollbarOffset(self, value):
		self.guiObject.setScrollbarOffset(parseInteger(value))

	def scrollbarRadius(self, value):
		radius, edgeValue = parseRadius(value)
		self.guiObject.setScrollbarRadius(radius, edgeValue)

	def scrollbarScroll(self, value):
		self.guiObject.setScrollbarScroll(parseScrollbarScroll(value))

	def scrollbarSliderBorderColor(self, value):  # This legacy definition uses an inconsistent name, use'scrollbarBorderColor' instead!
		self.scrollbarBorderColor(value)
		attribDeprecationWarning("scrollbarSliderBorderColor", "scrollbarBorderColor")

	def scrollbarSliderBorderWidth(self, value):  # This legacy definition uses an inconsistent name, use'scrollbarBorderWidth' instead!
		self.scrollbarBorderWidth(value)
		attribDeprecationWarning("scrollbarSliderBorderWidth", "scrollbarBorderWidth")

	def scrollbarSliderForegroundColor(self, value):  # This legacy definition uses an inconsistent name, use'scrollbarForegroundColor' instead!
		self.scrollbarForegroundColor(value)
		attribDeprecationWarning("scrollbarSliderForegroundColor", "scrollbarForegroundColor")

	def scrollbarSliderPicture(self, value):  # This legacy definition uses an inconsistent name, use'scrollbarForegroundPixmap' instead!
		self.scrollbarForegroundPixmap(value)
		attribDeprecationWarning("scrollbarSliderPicture", "scrollbarForegroundPixmap")

	def scrollbarSliderPixmap(self, value):  # This legacy definition uses an inconsistent name, use'scrollbarForegroundPixmap' instead!
		self.scrollbarForegroundPixmap(value)
		attribDeprecationWarning("scrollbarSliderPixmap", "scrollbarForegroundPixmap")

	def scrollbarWidth(self, value):
		self.guiObject.setScrollbarWidth(self.applyHorizontalScale(value))

	def secondFont(self, value):
		self.valueFont(value)
		attribDeprecationWarning("secondFont", "valueFont")

	def secondfont(self, value):  # This legacy definition uses an inconsistent name, use 'secondFont' instead!
		self.valueFont(value)
		attribDeprecationWarning("secondfont", "valueFont")

	def seek_pointer(self, value):  # This legacy definition uses an inconsistent name, use 'seekPointer' instead!
		self.seekPointer(value)
		# attribDeprecationWarning("seek_pointer", "seekPointer")

	def seekPointer(self, value):
		(name, pos) = (x.strip() for x in value.split(":", 1))
		ptr = parsePixmap(name, self.desktop)
		pos = parsePosition(pos, self.scaleTuple)
		self.guiObject.setPointer(1, ptr, pos)

	def selection(self, value):
		self.guiObject.setSelectionEnable(1 if parseBoolean("selection", value) else 0)

	def selectionDisabled(self, value):  # This legacy definition is a redundant option and is uncharacteristic, use 'selection="0"' etc instead!
		self.guiObject.setSelectionEnable(0 if parseBoolean("selection", value) else 1)
		# attribDeprecationWarning("selectionDisabled", "selection")

	def selectionPixmap(self, value):
		self.guiObject.setSelectionPixmap(parsePixmap(value, self.desktop))

	def selectionZoom(self, value):
		data = [x.strip() for x in value.split(",")]
		value = parseInteger(data[0], 0)
		if value > 500:
			value = 500
		mode = parseZoom(data[1], "selectionZoom") if len(data) == 2 else eListbox.zoomContentZoom
		self.guiObject.setSelectionZoom(float(f"{(value // 100) + 1}.{value % 100:02}"), mode)

	def selectionZoomSize(self, value):
		data = [x.strip() for x in value.split(",")]
		size = parseValuePair(f"{data[0]},{data[1]}", self.scaleTuple, self.guiObject, self.desktop)
		mode = parseZoom(data[2], "selectionZoomSize") if len(data) == 3 else eListbox.zoomContentZoom
		self.guiObject.setSelectionZoomSize(size[0], size[1], mode)

	def shadowColor(self, value):
		self.guiObject.setShadowColor(parseColor(value, 0x00000000))

	def shadowOffset(self, value):
		self.guiObject.setShadowOffset(parsePosition(value, self.scaleTuple))

	def size(self, value):
		self.guiObject.resize(eSize(*value) if isinstance(value, tuple) else parseSize(value, self.scaleTuple, self.guiObject, self.desktop))

	def sliderPixmap(self, value):  # For compatibility same as 'scrollbarSliderPixmap', use 'scrollbarForegroundPixmap' instead.
		self.scrollbarForegroundPixmap(value)
		attribDeprecationWarning("sliderPixmap", "scrollbarForegroundPixmap")

	def spacingColor(self, value):
		self.guiObject.setSpacingColor(parseColor(value, 0x00000000))

	def text(self, value):
		if value:
			value = _(value)
		self.guiObject.setText(value)

	def textBorderColor(self, value):
		self.guiObject.setTextBorderColor(parseColor(value, 0x00FFFFFF))

	def textBorderWidth(self, value):
		self.guiObject.setTextBorderWidth(self.applyVerticalScale(value))

	def textOffset(self, value):
		self.textPadding(value)
		attribDeprecationWarning("textOffset", "textPadding")

	def textPadding(self, value):
		leftPadding, topPadding, rightPadding, bottomPadding = parsePadding("textPadding", value)
		self.guiObject.setTextPadding(eRect(self.applyHorizontalScale(leftPadding), self.applyVerticalScale(topPadding), self.applyHorizontalScale(rightPadding), self.applyVerticalScale(bottomPadding)))

	def title(self, value):
		if value:
			value = _(value)
		self.guiObject.setTitle(value)

	def transparent(self, value):
		self.guiObject.setTransparent(1 if parseBoolean("transparent", value) else 0)

	def vAlign(self, value):  # This typo catcher definition uses an inconsistent name, use 'verticalAlignment' instead!
		self.verticalAlignment(value)
		# attribDeprecationWarning("vAlign", "verticalAlignment")

	def valign(self, value):  # This legacy definition uses an inconsistent name, use 'verticalAlignment' instead!
		self.verticalAlignment(value)
		# attribDeprecationWarning("valign", "verticalAlignment")

	def valueFont(self, value):
		self.guiObject.setValueFont(parseFont(value, self.scaleTuple))

	def verticalAlignment(self, value):
		self.guiObject.setVAlign(parseVerticalAlignment(value))

	def widgetBorderColor(self, value):
		self.guiObject.setWidgetBorderColor(parseColor(value, 0x00FFFFFF))

	def widgetBorderWidth(self, value):
		self.guiObject.setWidgetBorderWidth(self.applyVerticalScale(value))

	def wrap(self, value):
		self.guiObject.setWrap(parseWrap(value))

	def zPosition(self, value):
		self.guiObject.setZPosition(parseInteger(value))


def applyAllAttributes(guiObject, desktop, attributes, scale=((1, 1), (1, 1))):
	AttributeParser(guiObject, desktop, scale).applyAll(attributes)


def reloadWindowStyles():
	for screenID in windowStyles:
		loadSingleSkinData(*windowStyles[screenID])


def loadSingleSkinData(desktop, screenID, domSkin, pathSkin, scope=SCOPE_GUISKIN):
	"""Loads skin data like colors, windowstyle etc."""
	assert domSkin.tag == "skin", "root element in skin must be 'skin'!"
	global colors, fonts, menus, parameters, setups, switchPixmap, resolutions, scrollLabelStyle
	for tag in domSkin.findall("output"):
		scrnID = parseInteger(tag.attrib.get("id", GUI_SKIN_ID), GUI_SKIN_ID)
		if scrnID == GUI_SKIN_ID:
			for res in tag.findall("resolution"):
				xres = parseInteger(res.attrib.get("xres", 720), 720)
				yres = parseInteger(res.attrib.get("yres", 576), 576)
				bpp = parseInteger(res.attrib.get("bpp", 32), 32)
				resolutions[scrnID] = (xres, yres, bpp)
				if bpp != 32:
					pass  # Load palette (Not yet implemented!)
	for tag in domSkin.findall("include"):
		filename = tag.attrib.get("filename")
		if filename:
			resolved = resolveFilename(scope, filename, path_prefix=pathSkin)
			if isfile(resolved):
				loadSkin(resolved, scope=scope, desktop=desktop, screenID=screenID)
			else:
				skinError(f"Tag 'include' needs an existing filename, got filename '{filename}' ({resolved})")
	for tag in domSkin.findall("switchpixmap"):
		for pixmap in tag.findall("pixmap"):
			name = pixmap.attrib.get("name")
			filename = pixmap.attrib.get("filename")
			resolved = resolveFilename(scope, filename, path_prefix=pathSkin)
			if name and isfile(resolved):
				switchPixmap[name] = LoadPixmap(resolved, cached=True)
			else:
				skinError(f"Tag 'pixmap' needs a name and existing filename, got name='{name}' and filename='{filename}' ({resolved})")
	for tag in domSkin.findall("colors"):
		for color in tag.findall("color"):
			name = color.attrib.get("name")
			color = color.attrib.get("value")
			if name and color:
				colors[name] = parseColor(color, 0x00FFFFFF)
			else:
				skinError(f"Tag 'color' needs a name and color, got name='{name}' and color='{color}'")
	for tag in domSkin.findall("fonts"):
		for font in tag.findall("font"):
			filename = font.attrib.get("filename", "<NONAME>")
			name = font.attrib.get("name", "Regular")
			scale = font.attrib.get("scale")
			scale = int(scale) if scale and scale.isdigit() else 100
			isReplacement = font.attrib.get("replacement") and True or False
			render = font.attrib.get("render")
			render = int(render) if render and render.isdigit() else 0
			resolved = resolveFilename(SCOPE_FONTS, filename, path_prefix=pathSkin)
			if isfile(resolved) and name:
				addFont(resolved, name, scale, isReplacement, render)
				# Log provided by C++ addFont code.
				# print(f"[Skin] DEBUG: Font filename='{filename}', path='{resolved}', name='{name}', scale={scale}, isReplacement={isReplacement}, render={render}.")
			else:
				skinError(f"Tag 'font' needs an existing filename and name, got filename='{filename}' ({resolved}) and name='{name}'")
		fallbackFont = resolveFilename(SCOPE_FONTS, "fallback.font", path_prefix=pathSkin)
		if isfile(fallbackFont):
			addFont(fallbackFont, "Fallback", 100, -1, 0)
		for alias in tag.findall("alias"):
			name = alias.attrib.get("name")
			font = alias.attrib.get("font")
			size = parseInteger(alias.attrib.get("size", 20), 20)
			height = parseInteger(alias.attrib.get("height", 25), 25)  # To be calculated some day.
			width = parseInteger(alias.attrib.get("width", 18), 18)  # To be calculated some day.
			if name and font and size:
				fonts[name] = (font, size, height, width)
				# print(f"[Skin] Add font alias: name='{name}', font='{font}', size={size}, height={height}, width={width}.")
			else:
				skinError(f"Tag 'alias' needs a name, font and size, got name='{name}', font'{font}' and size='{size}'")
	for tag in domSkin.findall("parameters"):
		for parameter in tag.findall("parameter"):
			name = parameter.attrib.get("name")
			value = parameter.attrib.get("value")
			if name and value:
				parameters[name] = list(map(parseParameter, [x.strip() for x in value.split(",")])) if "," in value else parseParameter(value)
			else:
				skinError(f"Tag 'parameter' needs a name and value, got name='{name}' and size='{value}'")
	for tag in domSkin.findall("menus"):
		for setup in tag.findall("menu"):
			key = setup.attrib.get("key")
			image = setup.attrib.get("image")
			if key and image:
				menus[key] = image
				# print(f"[Skin] DEBUG: Menu key='{key}', image='{image}'.")
			else:
				skinError(f"Tag 'menu' needs key and image, got key='{key}' and image='{image}'")
	for tag in domSkin.findall("setups"):
		for setup in tag.findall("setup"):
			key = setup.attrib.get("key")
			image = setup.attrib.get("image")
			if key and image:
				setups[key] = image
				# print(f"[Skin] DEBUG: Setup key='{key}', image='{image}'.")
			else:
				skinError(f"Tag 'setup' needs key and image, got key='{key}' and image='{image}'")
	for tag in domSkin.findall("constant-widgets"):
		for constant_widget in tag.findall("constant-widget"):
			name = constant_widget.attrib.get("name")
			if name:
				constantWidgets[name] = constant_widget
	for tag in domSkin.findall("layouts"):
		for layout in tag.findall("layout"):
			name = layout.attrib.get("name")
			if name:
				layouts[name] = layout
	for tag in domSkin.findall("variables"):
		for parameter in tag.findall("variable"):
			name = parameter.attrib.get("name")
			value = parameter.attrib.get("value")
			xValue, yValue = value.split(",")
			if value and name:
				variables[name] = f"{str(xValue)},{str(yValue)}"
	for tag in domSkin.findall("subtitles"):
		for substyle in tag.findall("sub"):
			face = eSubtitleWidget.__dict__[substyle.attrib.get("name")]
			font = parseFont(substyle.attrib.get("font"), scale=((1, 1), (1, 1)))
			foregroundColor = substyle.attrib.get("foregroundColor")
			if foregroundColor:
				haveColor = 1
				foregroundColor = parseColor(foregroundColor, 0x00FFFFFF)
			else:
				haveColor = 0
				foregroundColor = gRGB(0x00FFFFFF)
			borderColor = parseColor(substyle.attrib.get("borderColor", substyle.attrib.get("shadowColor")), 0x00000000)
			borderWidth = parseInteger(substyle.attrib.get("borderWidth", 3), 3)  # Default: Use a subtitle border.
			eSubtitleWidget.setFontStyle(face, font, haveColor, foregroundColor, borderColor, borderWidth)
	colorNameConversions = {
		"LabelForeground": "Foreground",
		"ListboxMarkedBackground": "ListboxBackgroundMarked",
		"ListboxMarkedForeground": "ListboxForegroundMarked",
		"ListboxMarkedAndSelectedBackground": "ListboxBackgroundMarkedSelected",
		"ListboxMarkedAndSelectedForeground": "ListboxForegroundMarkedSelected",
		"ListboxSelectedBackground": "ListboxBackgroundSelected",
		"ListboxSelectedForeground": "ListboxForegroundSelected"
	}
	scrollbarModes = {
		eListbox.showOnDemand: "showOnDemand",
		eListbox.showAlways: "showAlways",
		eListbox.showNever: "showNever",
		eListbox.showLeftOnDemand: "showLeftOnDemand",
		eListbox.showLeftAlways: "showLeftAlways"
	}
	scrollbarScrolls = {
		0: "byPage",
		1: "byLine"
	}
	for tag in domSkin.findall("windowstyle"):
		style = eWindowStyleSkinned()
		for borderset in tag.findall("borderset"):
			bsName = str(borderset.attrib.get("name"))
			for pixmap in borderset.findall("pixmap"):
				bpName = pixmap.attrib.get("pos")
				filename = pixmap.attrib.get("filename")
				if filename and bpName:
					png = parsePixmap(resolveFilename(scope, filename, path_prefix=pathSkin), desktop)
					try:
						style.setPixmap(eWindowStyleSkinned.__dict__[bsName], eWindowStyleSkinned.__dict__[bpName], png)
					except Exception as err:
						skinError(f"Unknown style borderset name '{bpName}' ({err})")
		for color in tag.findall("color"):
			name = color.attrib.get("name")
			name = colorNameConversions.get(name, name)
			color = parseColor(color.attrib.get("color"), 0x00FFFFFF)
			if not isinstance(color, str):
				try:
					style.setColor(eWindowStyleSkinned.__dict__[f"col{name}"], color)
				except Exception as err:
					skinError(f"Unknown style color name '{name}' ({err})")
		for configList in tag.findall("configList"):
			style.setEntryFont(parseFont(configList.attrib.get("entryFont", "Regular;20"), ((1, 1), (1, 1))))
			style.setValueFont(parseFont(configList.attrib.get("valueFont", "Regular;20"), ((1, 1), (1, 1))))
		for label in tag.findall("label"):
			style.setLabelFont(parseFont(label.attrib.get("font", "Regular;20"), ((1, 1), (1, 1))))
		for listBox in tag.findall("listbox"):
			pageSize = parseInteger(listBox.attrib.get("pageSize", eListbox.DefaultPageSize), eListbox.DefaultPageSize)
			enableWrapAround = parseBoolean("enableWrapAround", listBox.attrib.get("enableWrapAround", "True" if eListbox.DefaultWrapAround else "False"))
			style.setListboxFont(parseFont(listBox.attrib.get("font", "Regular;20"), ((1, 1), (1, 1))))
			scrollbarBorderWidth = parseInteger(listBox.attrib.get("scrollbarBorderWidth", eListbox.DefaultScrollBarBorderWidth), eListbox.DefaultScrollBarBorderWidth)
			if "scrollbarBorderWidth" not in scrollLabelStyle:
				scrollLabelStyle["scrollbarBorderWidth"] = scrollbarBorderWidth
			scrollbarMode = parseScrollbarMode(listBox.attrib.get("scrollbarMode", scrollbarModes[eListbox.DefaultScrollBarMode]))
			if "scrollbarMode" not in scrollLabelStyle and scrollbarMode != eListbox.showNever:
				scrollLabelStyle["scrollbarMode"] = scrollbarMode
			scrollbarOffset = parseInteger(listBox.attrib.get("scrollbarOffset", eListbox.DefaultScrollBarOffset), eListbox.DefaultScrollBarOffset)
			if "scrollbarOffset" not in scrollLabelStyle:
				scrollLabelStyle["scrollbarOffset"] = scrollbarOffset
			scrollbarScroll = parseScrollbarScroll(listBox.attrib.get("scrollbarScroll", scrollbarScrolls[eListbox.DefaultScrollBarScroll]))
			if "scrollbarScroll" not in scrollLabelStyle:
				scrollLabelStyle["scrollbarScroll"] = scrollbarScroll
			scrollbarWidth = parseInteger(listBox.attrib.get("scrollbarWidth", eListbox.DefaultScrollBarWidth), eListbox.DefaultScrollBarWidth)
			if "scrollbarWidth" not in scrollLabelStyle:
				scrollLabelStyle["scrollbarWidth"] = scrollbarWidth
			scrollbarRadius = parseRadius(listBox.attrib.get("scrollbarRadius", "0"))
			if "scrollbarRadius" not in scrollLabelStyle:
				scrollLabelStyle["scrollbarRadius"] = scrollbarRadius
			eListbox.setDefaultScrollbarStyle(scrollbarWidth, scrollbarOffset, scrollbarBorderWidth, scrollbarScroll, scrollbarMode, enableWrapAround, pageSize)
			eListbox.setDefaultScrollbarRadius(*scrollbarRadius)
		for scrollLabel in tag.findall("scrolllabel"):
			scrollLabelStyle["scrollbarBorderWidth"] = parseInteger(scrollLabel.attrib.get("scrollbarBorderWidth", eListbox.DefaultScrollBarBorderWidth), eListbox.DefaultScrollBarBorderWidth)
			scrollLabelStyle["scrollbarMode"] = parseScrollbarMode(scrollLabel.attrib.get("scrollbarMode", scrollbarModes[eListbox.showOnDemand]))
			scrollLabelStyle["scrollbarOffset"] = parseInteger(scrollLabel.attrib.get("scrollbarOffset", eListbox.DefaultScrollBarOffset), eListbox.DefaultScrollBarOffset)
			scrollLabelStyle["scrollbarScroll"] = parseScrollbarScroll(scrollLabel.attrib.get("scrollbarScroll", scrollbarScrolls[eListbox.DefaultScrollBarScroll]))
			scrollLabelStyle["scrollbarWidth"] = parseInteger(scrollLabel.attrib.get("scrollbarWidth", eListbox.DefaultScrollBarWidth), eListbox.DefaultScrollBarWidth)
			scrollLabelStyle["scrollbarRadius"] = parseRadius(scrollLabel.attrib.get("scrollbarRadius", "0"))
		for slider in tag.findall("slider"):
			borderWidth = parseInteger(slider.attrib.get("borderWidth", eSlider.DefaultBorderWidth), eSlider.DefaultBorderWidth)
			eSlider.setDefaultBorderWidth(borderWidth)
		for stringList in tag.findall("stringList"):
			eListbox.setDefaultPadding(eRect(*parsePadding("textPadding", stringList.attrib.get("textPadding", "0,0,0,0"))))
		for title in tag.findall("title"):
			style.setTitleFont(parseFont(title.attrib.get("font", "Regular;20"), ((1, 1), (1, 1))))
			style.setTitleOffset(parseSize(title.attrib.get("offset", "20,5"), ((1, 1), (1, 1))))
		instance = eWindowStyleManager.getInstance()
		instance.setStyle(parseInteger(tag.attrib.get("id", GUI_SKIN_ID), GUI_SKIN_ID), style)
	for tag in domSkin.findall("margin"):
		rectange = eRect(0, 0, 0, 0)
		value = tag.attrib.get("left")
		if value:
			rectange.setLeft(parseInteger(value))
		value = tag.attrib.get("top")
		if value:
			rectange.setTop(parseInteger(value))
		value = tag.attrib.get("right")
		if value:
			rectange.setRight(parseInteger(value))
		value = tag.attrib.get("bottom")
		if value:
			rectange.setBottom(parseInteger(value))
		# The "desktop" parameter is hard-coded to the GUI screen, so we must ask
		# for the one that this actually applies to.
		getDesktop(parseInteger(tag.attrib.get("id", GUI_SKIN_ID))).setMargins(rectange)


class additionalWidget:
	def __init__(self):
		pass


# Class that makes a tuple look like something else. Some plugins just assume
# that size is a string and try to parse it. This class makes that work.
#
class SizeTuple(tuple):
	def __str__(self):
		return "%s,%s" % self

	def split(self, *args):
		return str(self[0]), str(self[1])

	def strip(self, *args):
		return "%s,%s" % self


class SkinContext:
	def __init__(self, parent=None, pos=None, size=None, font=None):
		if parent:
			if pos is None:
				self.x = None
				self.y = None
				self.w = None
				self.h = None
				self.scale = ((1, 1), (1, 1))
			else:
				pos, size = parent.parse(pos, size, font)
				self.x, self.y = pos
				self.w, self.h = size
				self.scale = parent.scale
		else:
			self.x = None
			self.y = None
			self.w = None
			self.h = None
			self.scale = ((1, 1), (1, 1))
		# print(f"[Skin] SkinContext DEBUG: parent={parent}, pos={pos}, size={size}, x={self.x}, y={self.y}, w={self.w}, h={self.h}, scale={self.scale}.")

	def __str__(self):
		return f"Context ({self.x},{self.y})+({self.w},{self.h})"

	def parse(self, pos, size, font):
		if size in variables:
			size = variables[size]
		if pos == "fill":
			pos = (self.x, self.y)
			size = (self.w, self.h)
			self.w = 0
			self.h = 0
		else:
			(width, height) = size.split(",")
			width = parseCoordinate(width, self.w, 0, font, self.scale[0])
			height = parseCoordinate(height, self.h, 0, font, self.scale[1])
			if pos == "bottom":
				pos = (self.x, self.y + self.h - height)
				size = (self.w, height)
				self.h -= height
			elif pos == "top":
				pos = (self.x, self.y)
				size = (self.w, height)
				self.h -= height
				self.y += height
			elif pos == "left":
				pos = (self.x, self.y)
				size = (width, self.h)
				self.x += width
				self.w -= width
			elif pos == "right":
				pos = (self.x + self.w - width, self.y)
				size = (width, self.h)
				self.w -= width
			else:
				if pos in variables:
					pos = variables[pos]
				size = (width, height)
				pos = pos.split(",")
				pos = (self.x + parseCoordinate(pos[0], self.w, size[0], font, self.scale[0]), self.y + parseCoordinate(pos[1], self.h, size[1], font, self.scale[1]))
		# print(f"[Skin] SkinContext DEBUG: Scale={self.scale}, Pos={SizeTuple(pos)}, Size={SizeTuple(size)}.")
		return (SizeTuple(pos), SizeTuple(size))


# A context that stacks things instead of aligning them.
#
class SkinContextStack(SkinContext):
	def parse(self, pos, size, font):
		if size in variables:
			size = variables[size]
		if pos == "fill":
			pos = (self.x, self.y)
			size = (self.w, self.h)
		else:
			(width, height) = size.split(",")
			width = parseCoordinate(width, self.w, 0, font, self.scale[0])
			height = parseCoordinate(height, self.h, 0, font, self.scale[1])
			if pos == "bottom":
				pos = (self.x, self.y + self.h - height)
				size = (self.w, height)
			elif pos == "top":
				pos = (self.x, self.y)
				size = (self.w, height)
			elif pos == "left":
				pos = (self.x, self.y)
				size = (width, self.h)
			elif pos == "right":
				pos = (self.x + self.w - width, self.y)
				size = (width, self.h)
			else:
				if pos in variables:
					pos = variables[pos]
				size = (width, height)
				pos = pos.split(",")
				pos = (self.x + parseCoordinate(pos[0], self.w, size[0], font, self.scale[0]), self.y + parseCoordinate(pos[1], self.h, size[1], font, self.scale[1]))
		# print(f"[Skin] SkinContextStack DEBUG: Scale={self.scale}, Pos={SizeTuple(pos)}, Size={SizeTuple(size)}.")
		return (SizeTuple(pos), SizeTuple(size))


class SkinError(Exception):
	def __init__(self, errorMessage):
		self.errorMessage = errorMessage

	def __str__(self):
		return f"[Skin] Error: {self.errorMessage}!"


def readSkin(screen, skin, names, desktop):
	if not isinstance(names, list):
		names = [names]
	for name in names:  # Try all skins, first existing one has priority.
		myScreen, path = domScreens.get(name, (None, None))
		if myScreen is not None:
			if screen.mandatoryWidgets is None:
				screen.mandatoryWidgets = []
			else:
				widgets = findWidgets(name)
			if screen.mandatoryWidgets == [] or all(item in widgets for item in screen.mandatoryWidgets):
				myName = name  # Use this name for debug output.
				break
			else:
				widgetList = ", ".join(screen.mandatoryWidgets)
				print(f"[Skin] Warning: Skin screen '{name}' rejected as it does not offer all the mandatory widgets '{widgetList}'!")
				myScreen = None
	else:
		myName = f"<embedded-in-{screen.__class__.__name__}>"
	if myScreen is None:  # Otherwise try embedded skin.
		myScreen = getattr(screen, "parsedSkin", None)
	if myScreen is None and getattr(screen, "skin", None):  # Try uncompiled embedded skin.
		if isinstance(screen.skin, list):
			print(f"[Skin] Resizable embedded skin template found in '{myName}'.")
			skin = screen.skin[0] % tuple([int(x * getSkinFactor()) for x in screen.skin[1:]])
		else:
			skin = screen.skin
		print(f"[Skin] Parsing embedded skin '{myName}'.")
		if isinstance(skin, tuple):
			for xml in skin:
				candidate = fromstring(xml)
				if candidate.tag == "screen":
					screenID = candidate.attrib.get("id")
					if (not screenID) or (parseInteger(screenID) == DISPLAY_SKIN_ID):
						myScreen = candidate
						break
			else:
				print("[Skin] No suitable screen found!")
		else:
			myScreen = fromstring(skin)
		if myScreen:
			screen.parsedSkin = myScreen
	if myScreen is None:
		print("[Skin] No skin to read or screen to display.")
		myScreen = screen.parsedSkin = fromstring("<screen></screen>")
	screen.skinAttributes = []
	skinPath = getattr(screen, "skin_path", path)  # TODO: It may be possible for "path" to be undefined!
	context = SkinContextStack()
	bounds = desktop.bounds()
	context.x = bounds.left()
	context.y = bounds.top()
	context.w = bounds.width()
	context.h = bounds.height()
	resolution = tuple([parseInteger(x.strip()) for x in myScreen.attrib.get("resolution", f"{context.w},{context.h}").split(",")])
	context.scale = ((context.w, resolution[0]), (context.h, resolution[1]))
	del bounds
	collectAttributes(screen.skinAttributes, myScreen, context, skinPath, ignore=("name",))
	context = SkinContext(context, myScreen.attrib.get("position"), myScreen.attrib.get("size"))
	screen.additionalWidgets = []
	screen.renderer = []
	usedComponents = set()

	def processConstant(constant_widget, context):
		widgetName = constant_widget.attrib.get("name")
		if widgetName:
			try:
				constantWidgetValues = constantWidgets[widgetName]
			except KeyError:
				raise SkinError(f"Given constant-widget '{widgetName}' not found in skin")
		if constantWidgetValues:
			for value in constantWidgetValues:
				myScreen.append((value))
		try:
			myScreen.remove(constant_widget)
		except ValueError:
			pass

	def processLayouts(layout, context):
		widgetName = layout.attrib.get("name")
		if widgetName:
			try:
				constantWidgetValues = layouts[widgetName]
			except KeyError:
				raise SkinError(f"Given layout '{widgetName}' not found in skin")
		if constantWidgetValues:
			for value in constantWidgetValues:
				myScreen.append((value))
		try:
			myScreen.remove(layout)
		except ValueError:
			pass

	def processNone(widget, context):
		pass

	def processWidget(widget, context):
		# Okay, we either have 1:1-mapped widgets ("old style"), or 1:n-mapped
		# widgets (source->renderer).
		widgetName = widget.attrib.get("name")
		widgetSource = widget.attrib.get("source")
		if widgetName is None and widgetSource is None:
			raise SkinError("The widget has no name and no source")
			return
		if widgetName:
			# print(f"[Skin] DEBUG: Widget name='{widgetName}'.")
			usedComponents.add(widgetName)
			try:  # Get corresponding "gui" object.
				attributes = screen[widgetName].skinAttributes = []
			except Exception:
				raise SkinError(f"Component with name '{widgetName}' was not found in skin of screen '{myName}'")
			# assert screen[widgetName] is not Source
			collectAttributes(attributes, widget, context, skinPath, ignore=("name",))
		elif widgetSource:
			# print(f"[Skin] DEBUG: Widget source='{widgetSource}'.")
			while True:  # Get corresponding source until we found a non-obsolete source.
				# Parse our current "widgetSource", which might specify a "related screen" before the dot,
				# for example to reference a parent, global or session-global screen.
				scr = screen
				path = widgetSource.split(".")  # Resolve all path components.
				while len(path) > 1:
					scr = screen.getRelatedScreen(path[0])
					if scr is None:
						raise SkinError(f"Specified related screen '{widgetSource}' was not found in screen '{myName}'")
					path = path[1:]
				source = scr.get(path[0])  # Resolve the source.
				if isinstance(source, ObsoleteSource):
					# If we found an "obsolete source", issue warning, and resolve the real source.
					print(f"[Skin] WARNING: SKIN '{myName}' USES OBSOLETE SOURCE '{widgetSource}', USE '{source.newSource}' INSTEAD!")
					print(f"[Skin] OBSOLETE SOURCE WILL BE REMOVED {source.removalDate}, PLEASE UPDATE!")
					if source.description:
						print(f"[Skin] Source description: '{source.description}'.")
					widgetSource = source.new_source
				else:
					break  # Otherwise, use the source.
			if source is None:
				raise SkinError(f"The source '{widgetSource}' was not found in screen '{myName}'")
			widgetRenderer = widget.attrib.get("render")
			if not widgetRenderer:
				raise SkinError(f"For source '{widgetSource}' a renderer must be defined with a 'render=' attribute")
			for converter in widget.findall("convert"):
				converterType = converter.get("type")
				assert converterType, "[Skin] The 'convert' tag needs a 'type' attribute!"
				# print(f"[Skin] DEBUG: Converter='{converterType}'.")
				try:
					parms = converter.text.strip()
				except Exception:
					parms = ""
				# print(f"[Skin] DEBUG: Params='{parms}'.")
				try:
					converterClass = my_import(".".join(("Components", "Converter", converterType))).__dict__.get(converterType)
				except ImportError as err:
					raise SkinError(f"Converter '{converterType}' not found")
				connection = None
				for element in source.downstream_elements:
					if isinstance(element, converterClass) and element.converter_arguments == parms:
						connection = element
				if connection is None:
					connection = converterClass(parms)
					connection.connect(source)
				source = connection
			try:
				rendererClass = my_import(".".join(("Components", "Renderer", widgetRenderer))).__dict__.get(widgetRenderer)
			except ImportError as err:
				raise SkinError(f"Renderer '{widgetRenderer}' not found")
			renderer = rendererClass()  # Instantiate renderer.
			renderer.connect(source)  # Connect to source.
			attributes = renderer.skinAttributes = []
			collectAttributes(attributes, widget, context, skinPath, ignore=("render", "source"))
			screen.renderer.append(renderer)

	def processApplet(widget, context):
		try:
			codeText = widget.text.strip()
			widgetType = widget.attrib.get("type")
			code = compile(codeText, "skin applet", "exec")
		except Exception as err:
			raise SkinError(f"Applet failed to compile: '{str(err)}'")
		if widgetType == "onLayoutFinish":
			screen.onLayoutFinish.append(code)
		else:
			raise SkinError(f"Applet type '{widgetType}' is unknown")

	def processLabel(widget, context):
		item = additionalWidget()
		item.widget = eLabel
		item.skinAttributes = []
		collectAttributes(item.skinAttributes, widget, context, skinPath, ignore=("name",))
		screen.additionalWidgets.append(item)

	def processPixmap(widget, context):
		item = additionalWidget()
		item.widget = ePixmap
		item.skinAttributes = []
		collectAttributes(item.skinAttributes, widget, context, skinPath, ignore=("name",))
		screen.additionalWidgets.append(item)

	def processRectangle(widget, context):
		item = additionalWidget()
		item.widget = eRectangle
		item.skinAttributes = []
		collectAttributes(item.skinAttributes, widget, context, skinPath, ignore=("name",))
		screen.additionalWidgets.append(item)

	def processScreen(widget, context):
		widgets = widget
		for widget in widgets.findall('constant-widget'):
			processConstant(widget, context)
		for layout in widgets.findall('layout'):
			processLayouts(layout, context)
		for widget in widgets:
			conditional = widget.attrib.get("conditional")
			if conditional and not [x for x in conditional.split(",") if x in screen.keys()]:
				continue
			objecttypes = widget.attrib.get("objectTypes", "").split(",")
			if len(objecttypes) > 1 and (objecttypes[0] not in screen.keys() or not [x for x in objecttypes[1:] if x == screen[objecttypes[0]].__class__.__name__]):
				continue
			includes = widget.attrib.get("includes")
			if includes and not [x for x in includes.split(",") if x in screen.keys()]:
				continue
			excludes = widget.attrib.get("excludes")
			if excludes and [x for x in excludes.split(",") if x in screen.keys()]:
				continue
			processor = processors.get(widget.tag, processNone)
			try:
				processor(widget, context)
			except SkinError as err:
				print(f"[Skin] Error in screen '{myName}' widget '{widget.tag}' {str(err)}!")

	def processPanel(widget, context):
		name = widget.attrib.get("name")
		if name:
			try:
				screen = domScreens[name]
			except KeyError:
				print(f"[Skin] Error: Unable to find screen '{name}' referred in screen '{myName}'!")
			else:
				processScreen(screen[0], context)
		layout = widget.attrib.get("layout")
		contextClass = SkinContextStack if layout == "stack" else SkinContext
		try:
			contextScreen = contextClass(context, widget.attrib.get("position"), widget.attrib.get("size"), widget.attrib.get("font"))
		except Exception as err:
			raise SkinError(f"Failed to create skin context (position='{widget.attrib.get('position')}', size='{widget.attrib.get('size')}', font='{widget.attrib.get('font')}') in context '{context}': {err}")
		processScreen(widget, contextScreen)

	processors = {
		None: processNone,
		"constant-widget": processConstant,
		"layout": processLayouts,
		"widget": processWidget,
		"applet": processApplet,
		"eLabel": processLabel,
		"ePixmap": processPixmap,
		"eRectangle": processRectangle,
		"panel": processPanel
	}

	try:
		msg = f" from list '{', '.join(names)}'" if len(names) > 1 else ""
		posX = "?" if context.x is None else str(context.x)
		posY = "?" if context.y is None else str(context.y)
		sizeW = "?" if context.w is None else str(context.w)
		sizeH = "?" if context.h is None else str(context.h)
		print(f"[Skin] Processing screen '{myName}'{msg}, position=({posX}, {posY}), size=({sizeW}x{sizeH}) for module '{screen.__class__.__name__}'.")
		context.x = 0  # Reset offsets, all components are relative to screen coordinates.
		context.y = 0
		processScreen(myScreen, context)
	except Exception as err:
		print(f"[Skin] Error in screen '{myName}' {str(err)}!")

	from Components.GUIComponent import GUIComponent
	unusedComponents = [x for x in set(screen.keys()) - usedComponents if isinstance(x, GUIComponent)]
	assert not unusedComponents, f"[Skin] The following components in '{myName}' don't have a skin entry: {', '.join(unusedComponents)}"
	# This may look pointless, but it unbinds "screen" from the nested scope. A better
	# solution is to avoid the nested scope above and use the context object to pass
	# things around.
	screen = None
	usedComponents = None


# Return a set of all the widgets found in a screen. Panels will be expanded
# recursively until all referenced widgets are captured. This code only performs
# a simple scan of the XML and no skin processing is performed.
#
def findWidgets(name):
	widgetSet = set()
	element, path = domScreens.get(name, (None, None))
	if element is not None:
		widgets = element.findall("widget")
		if widgets is not None:
			for widget in widgets:
				name = widget.get("name", None)
				if name is not None:
					widgetSet.add(name)
				source = widget.get("source", None)
				if source is not None:
					widgetSet.add(source)
		panels = element.findall("panel")
		if panels is not None:
			for panel in panels:
				name = panel.get("name", None)
				if name:
					widgetSet.update(findWidgets(name))
	return widgetSet


# This method emulates the C++ methods available to get Scrollbar style elements.
#
def getScrollLabelStyle(element):
	return scrollLabelStyle.get(element)


# Return a scaling factor (float) that can be used to rescale screen displays
# to suit the current resolution of the screen.  The scales are based on a
# default screen resolution of HD (720p).  That is the scale factor for a HD
# screen will be 1.
#
def getSkinFactor(screen=GUI_SKIN_ID):
	skinfactor = getDesktop(screen).size().height() / 720.0
	# if skinfactor not in [0.8, 1, 1.5, 3, 6]:
	# 	print(f"[Skin] Warning: Unexpected result for getSkinFactor '{skinfactor:.4f}'!")
	return skinfactor


# Search the domScreens dictionary to see if any of the screen names provided
# have a skin based screen.  This will allow coders to know if the named
# screen will be skinned by the skin code.  A return of None implies that the
# code must provide its own skin for the screen to be displayed to the user.
#
def findSkinScreen(names):
	if not isinstance(names, list):
		names = [names]
	for name in names:  # Try all names given, the first one found is the one that will be used by the skin engine.
		screen, path = domScreens.get(name, (None, None))
		if screen is not None:
			return name
	return None


def dump(x, i=0):
	print(" " * i + str(x))
	try:
		for node in x.childNodes:
			dump(node, i + 1)
	except Exception:
		pass
