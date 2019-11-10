# loosejson

A JSON parser for Python that shows more useful error messages and fixes minor formatting errors automatically.

If you use JSON files a lot, it can get very frustrating to get an error just because you failed to delete a trailing comma, or to be forced to write unreadable multi-line strings without linebreaks, or to get error messages that don't tell you directly what is actually causing the error.

Since I needed to make this process as user-friendly as possible for my startup elody.com, I wrote this convenience library to make it easier.

## Features

* Supports Unicode (implicitly, since it just uses whatever string format python is using)
* Supports escape characters like normal JSON does.
* Supports extra commas
* Supports unquoted strings for several kinds of characters that can often occur in Rules and Options
* Supports linebreaks in quoted strings (they are treated the same as writing \n, except that any spaces and tabs following them are ignored.)
* Supports both ' and " as quotation marks
* Supports both null and None, so it works for parsing both Javascript and Python
* Supports True/true, False/false
* Does not support infinite or NaN numbers
* Has useful error messages

This works for Python 2.7 and 3+.

## Installation

`pip install loosejson`

## Usage

`from loosejson import loosejson`

Just run `loosejson.parse_loosely_defined_json(text)` on a string. It returns a standard json object, just like json.loads(text), but with less of a headache.
