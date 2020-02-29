#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import time
import json
import argparse
import os
from datetime import datetime
import pytz
import calendar
from inky import InkyWHAT
from PIL import Image, ImageDraw, ImageFont
from font_fredoka_one import FredokaOne

try:
	import requests
except ImportError:
	exit("This script requires the requests module\nInstall with: sudo pip install requests")

icon_map = {
	"snow": ["snow", "sleet"],
	"rain": ["rain"],
	"cloud": ["fog", "cloudy", "partly-cloudy-day", "partly-cloudy-night"],
	"sun": ["clear-day", "clear-night"],
	"storm": [],
	"wind": ["wind"]
}

LARGE_FONT_SIZE = 20
MEDIUM_FONT_SIZE = 17
SMALL_FONT_SIZE = 15
SUMMARY_H = LARGE_FONT_SIZE * 2
FORECARST_COLUMNS = 3

def lookup_icon(icon_name):
	for icon in icon_map:
		if icon_name in icon_map[icon]:
			return icon

def get_weather(latitude, longitude, key):
	res = requests.get(f'https://api.darksky.net/forecast/{key}/{latitude},{longitude}?exclude=minutely,hourly,alerts,flags&units=si&lang=en')
	if res.status_code == 200:
		return res.json()
	else:
		return None

def create_mask(source, mask):
	"""Create a transparency mask.

	Takes a paletized source image and converts it into a mask
	permitting all the colours supported by Inky pHAT (0, 1, 2)
	or an optional list of allowed colours.

	:param mask: Optional list of Inky pHAT colours to allow.

	"""
	mask_image = Image.new("1", source.size)
	w, h = source.size
	for x in range(w):
		for y in range(h):
			p = source.getpixel((x, y))
			if p in mask:
				mask_image.putpixel((x, y), 255)
	return mask_image

def show_current_weather(draw, data_point, inky_display, h_offset):
	offset = h_offset
	font = ImageFont.truetype(FredokaOne, LARGE_FONT_SIZE)
	text_w, text_h = font.getsize(data_point['summary'])
	draw.text(( (inky_display.WIDTH - text_w) / 2, offset + (SUMMARY_H-text_h)/2), data_point['summary'], inky_display.RED, font=font)
	offset += SUMMARY_H
	font = ImageFont.truetype(FredokaOne, MEDIUM_FONT_SIZE)
	text_pressure = f'Pressure {round(data_point["pressure"], 1)}'
	text_pressure_w, text_pressure_h = font.getsize(text_pressure)
	draw.text(( (inky_display.WIDTH - text_pressure_w) / 2, offset), text_pressure, inky_display.BLACK, font=font)
	offset += LARGE_FONT_SIZE
	text_wind_speed = f'Wind speed {round(data_point["windSpeed"], 1)}'
	text_wind_speed_w, text_wind_speed_h  = font.getsize(text_wind_speed)
	draw.text(( (inky_display.WIDTH - text_wind_speed_w) / 2, offset), text_wind_speed, inky_display.BLACK, font=font)
	offset += LARGE_FONT_SIZE
	text_visibility = f'Visibility {round(data_point["visibility"], 1)}'
	text_visibility_w, text_visibility_h  = font.getsize(text_visibility)
	draw.text(( (inky_display.WIDTH - text_visibility_w) / 2, offset), text_visibility, inky_display.BLACK, font=font)
	offset += LARGE_FONT_SIZE
	text_ozone = f'Ozone {round(data_point["ozone"], 1)}'
	text_ozone_w, text_ozone_h  = font.getsize(text_ozone)
	draw.text(( (inky_display.WIDTH - text_ozone_w) / 2, offset), text_ozone, inky_display.BLACK, font=font)
	offset += LARGE_FONT_SIZE
	return offset + 10

def show_current_weather_icon(draw, img, data_point, inky_display, icons, masks, h_offset):
	font = ImageFont.truetype(FredokaOne, SMALL_FONT_SIZE)
	temp_text = f'{round(data_point["temperature"],1)}C feels like {round(data_point["apparentTemperature"],1)}C'
	text_w, text_h = font.getsize(temp_text)
	icon_name = lookup_icon(data_point['icon'])
	draw.rectangle((0, h_offset, inky_display.WIDTH, h_offset + icons[icon_name].height), fill=inky_display.BLACK)
	draw.text((8, h_offset + (icons[icon_name].height - text_h) / 2), temp_text, inky_display.WHITE, font=font)
	temp_text = f'Precip. chance: {round(data_point["precipProbability"],1)}%'
	text_w, text_h = font.getsize(temp_text)
	draw.text((inky_display.WIDTH - text_w - 8, h_offset + (icons[icon_name].height - text_h) / 2), temp_text, inky_display.WHITE, font=font)
	img.paste(icons[icon_name], ( int((inky_display.WIDTH - icon_image.width) / 2), h_offset), masks[icon_name])
	return h_offset + icons[icon_name].height

def draw_weather_tile(draw, img, data_point, icons, masks, timezone):
	time = datetime.fromtimestamp(data_point['time'], pytz.timezone(timezone))
	font = ImageFont.truetype(FredokaOne, MEDIUM_FONT_SIZE)
	time_text = f'{calendar.day_name[time.weekday()]}'
	time_text_w, time_text_h = font.getsize(time_text)
	draw.text((int((img.width - time_text_w) / 2), 0), time_text, inky_display.RED, font=font)
	icon_name = lookup_icon(data_point['icon'])
	draw.rectangle((0, time_text_h, img.width, time_text_h + icons[icon_name].height), fill=inky_display.BLACK)
	img.paste(icons[icon_name], (int((img.width - icons[icon_name].width) / 2), time_text_h), masks[icon_name])
	temp_text = f'{round(data_point["temperatureLow"],1)}C to {round(data_point["temperatureHigh"],1)}C'
	temp_text_w, temp_text_h = font.getsize(temp_text)
	draw.text(((img.width - temp_text_w) / 2, time_text_h + icons[icon_name].height), temp_text, inky_display.BLACK, align='center', font=font)


if __name__ == '__main__':
	PATH = os.path.dirname(__file__)
	icons = {}
	masks = {}

	parser = argparse.ArgumentParser()
	parser.add_argument('--colour', '-c', type=str, required=True, choices=["red", "black", "yellow"], help="ePaper display colour")
	parser.add_argument('--dskey', '-d', type=str, required=True, help="Dark sky secret api key")
	parser.add_argument('--latitude', '-l', type=str, required=True, help="Latitude of the location")
	parser.add_argument('--longitude', '-L', type=str, required=True, help="Longitude of the location")
	args = parser.parse_args()

	res = get_weather(args.latitude, args.longitude, args.dskey)
	#print(json.dumps(res, indent=2))

	colour = args.colour
	inky_display = InkyWHAT(colour)
	for icon in glob.glob(os.path.join(PATH, "weather_resources/icon-*.png")):
		icon_name = icon.split("icon-")[1].replace(".png", "")
		icon_image = Image.open(icon)
		icons[icon_name] = icon_image
		masks[icon_name] = create_mask(icon_image, (inky_display.WHITE, inky_display.BLACK, inky_display.RED))

	img = Image.new("P", (inky_display.WIDTH, inky_display.HEIGHT), inky_display.WHITE)
	draw = ImageDraw.Draw(img)
	used_h = show_current_weather(draw, res['currently'], inky_display , 0)
	used_h = show_current_weather_icon(draw, img, res['currently'], inky_display, icons, masks, used_h)
	tile_w = int(inky_display.WIDTH / FORECARST_COLUMNS)
	tile_h = int(inky_display.HEIGHT - used_h)
	for i in range(FORECARST_COLUMNS):
		tile = Image.new("P", (tile_w, tile_h), inky_display.WHITE)
		tile_draw = ImageDraw.Draw(tile)
		draw_weather_tile(tile_draw, tile, res['daily']['data'][i], icons, masks, res['timezone'])
		img.paste(tile, (i * tile_w, used_h))
	font = ImageFont.truetype(FredokaOne, SMALL_FONT_SIZE)
	timestamp = f'Data loaded at {datetime.now(pytz.timezone(res["timezone"])).strftime("%H:%M:%S %d %b %Y")}'
	draw.text((8, inky_display.HEIGHT - SMALL_FONT_SIZE), timestamp, inky_display.RED, font=font)
	inky_display.set_image(img.rotate(180))
	inky_display.show()
