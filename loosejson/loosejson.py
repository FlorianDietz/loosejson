import ast
import json
import math
import re
import sys
import traceback

from six import string_types

##############################################################################################################
# This is a JSON parser that isn't as strict as the normal json libraries.
# I can't believe a library for this didn't already exist and I had to write it myself...
##############################################################################################################


class JsonParsingException(Exception):
    pass


def parse_loosely_defined_json(text):
    """
    This function parses a string that represents a JSON object and isn't as strict as the normal json libraries.
    It has the following features:
    * Supports Unicode (implicitly, since it just uses whatever string format python is using)
    * Supports escape characters like normal JSON does.
    * Supports extra commas
    * Supports unquoted strings for several kinds of characters that can often occur in Rules and Options
    * Supports linebreaks in quoted strings (they are treated the same as writing \n, except that any spaces and tabs following them are ignored.)
    * Supports both ' and " as quotation marks
    * Supports both null and None, so it works for parsing both Javascript and Python
    * Supports True/true and False/false for the same reason
    * Does not support infinite or NaN numbers
    * Has useful error messages
    """
    parser = LooseJsonParser(text)
    raised_error = None
    try:
        res = parser.get_object()
    except Exception as e:
        # don't raise the exception here directly because python will "helpfully" chain the exceptions together
        raised_error = e
        raised_error_details = get_error_message_details()
    if raised_error is not None:
        raise JsonParsingException("exception while parsing text into JSON format.\nException occured at line %d, column %d, for character '%s':\n%s" % (parser.line, parser.col, parser.chars[parser.pos], str(raised_error),))
    # convert to JSON string and back again, just to be sure it works and any error arises now and not later
    res = json.loads(json.dumps(res))
    return res


class LooseJsonParser:
    def __init__(self, text):
        self.pos = 0
        self.line = 1
        self.col = 1
        self.chars = list(text)
        self.unquoted_characters = '[a-zA-Z0-9.?!\-_]'
        self.EOF = object()
        self.chars.append(self.EOF)
    def get_object(self):
        """
        Starting at the current position, continues parsing new characters until it has parsed a complete object, then returns that object.
        When this starts, self.pos should be at the first character of the object (or leading whitespace)
        and when it returns self.pos will be at the last character of the object.
        """
        task = None
        while self.pos < len(self.chars):
            char = self.chars[self.pos]
            if char == self.EOF:
                raise JsonParsingException("reached the end of the file without encountering anything to parse.")
            # update line and column on a linebreak
            if char == '\n':
                self.line += 1
                self.col = 1
            # how to handle the character depends on what is currently being done
            if task is None:
                if re.match('\s', char):
                    # while there is no task yet, ignore whitespace and continue looking for an object
                    pass
                elif char == '[':
                    task = 'building_list'
                    res_builder = []
                    expecting_comma = False
                elif char == '{':
                    task = 'building_dict'
                    res_builder = {}
                    stage = 'expecting_key'
                elif char == '"':
                    task = 'building_primitive'
                    quote_type = 'double_quotes'
                    res_builder = []
                    string_escape = False
                elif char == "'":
                    task = 'building_primitive'
                    quote_type = 'single_quotes'
                    res_builder = []
                    string_escape = False
                elif re.match(self.unquoted_characters, char):
                    task = 'building_primitive'
                    quote_type = 'no_quotes'
                    res_builder = [char]
                    string_escape = False
                    is_finished, res = self._unquoted_text_lookahead_and_optionally_finish(res_builder)
                    if is_finished:
                        return res
                else:
                    raise JsonParsingException("reached an unexpected character while looking for the start of the next object: %s" % char)
            elif task == 'building_list':
                if re.match('\s', char):
                    pass # skip whitespace in a list
                elif char == ',':
                    if expecting_comma:
                        expecting_comma = False
                    else:
                        raise JsonParsingException("encountered multiple commas after another while parsing a list. Did you forget a list element?")
                elif char == ']':
                    # the end of the list has been reached.
                    return res_builder
                else:
                    if expecting_comma:
                        raise JsonParsingException("expected a comma before the next list element.")
                    else:
                        # recurse to get the next element
                        next_list_element = self.get_object()
                        res_builder.append(next_list_element)
                        expecting_comma = True
            elif task == 'building_dict':
                if re.match('\s', char):
                    pass # skip whitespace in a dictionary
                elif char == '}':
                    if stage in ['expecting_key', 'expecting_comma']:
                        return res_builder
                    else:
                        raise JsonParsingException("the dictionary was closed too early. It's missing a value to go with the last key.")
                else:
                    if stage == 'expecting_key':
                        # recurse to get the next element, and verify it's a string and it's new
                        next_dict_key = self.get_object()
                        if not isinstance(next_dict_key, string_types):
                            # if the key is not a string, but is a primitive, coerce it into a string representing the JSON object
                            # (this uses str(json.dumps(next_dict_key)) instead of just str() so that None/null get turned to 'null' instead of 'None')
                            if isinstance(next_dict_key, (int, float, bool)):
                                next_dict_key = str(json.dumps(next_dict_key))
                        if next_dict_key in res_builder:
                            raise JsonParsingException("this string has already been used as a key of this dictionary. No duplicate keys are allowed:\n%s" % next_dict_key)
                        stage = 'expecting_colon'
                    elif stage == 'expecting_colon':
                        if char == ':':
                            stage = 'expecting_value'
                        else:
                            raise JsonParsingException("expected a colon separating the dictionary's key from its value")
                    elif stage == 'expecting_value':
                        # recurse to get the next element
                        next_dict_value = self.get_object()
                        res_builder[next_dict_key] = next_dict_value
                        stage = 'expecting_comma'
                    elif stage == 'expecting_comma':
                        if char == ',':
                            stage = 'expecting_key'
                        else:
                            raise JsonParsingException("expected a comma before the next dictionary key.")
                    else:
                        raise Exception("Programming error: undefined stage of dictionary parsing: %s" % stage)
            elif task == 'building_primitive':
                if quote_type in ['double_quotes', 'single_quotes']:
                    if quote_type == 'double_quotes':
                        limiting_quote = '"'
                    else:
                        limiting_quote = "'"
                    if char == limiting_quote and not string_escape:
                        # the end of the string has been reached. Build the string.
                        # before evaluating the string, do some preprocessing that makes linebreaks possible
                        tmp = []
                        encountered_linebreak = False
                        for chr in res_builder:
                            if chr == '\n':
                                encountered_linebreak = True
                                tmp.append('\\')
                                tmp.append('n')
                            elif (chr == ' ' or chr == '\t') and encountered_linebreak:
                                # ignore any spaces and tabs following a linebreak
                                pass
                            else:
                                encountered_linebreak = False
                                tmp.append(chr)
                        # combine the characters into a string and evaluate it
                        res = "".join(tmp)
                        res = ast.literal_eval(limiting_quote + res + limiting_quote)
                        return res
                    # add the current character to the list
                    # (we already know it's valid because of an earlier call to
                    # self._unquoted_text_lookahead_and_optionally_finish())
                    res_builder.append(char)
                    # if a backslash occurs, enter escape mode unless escape mode is already active,
                    # else deactivate escape mode
                    if char == '\\' and not string_escape:
                        string_escape = True
                    else:
                        string_escape = False
                elif quote_type == 'no_quotes':
                    if not re.match(self.unquoted_characters, char):
                        raise Exception("Programming error: this should have never been reached because of _unquoted_text_lookahead_and_optionally_finish().")
                    # add the element
                    res_builder.append(char)
                    # look ahead, and possibly finish up
                    is_finished, res = self._unquoted_text_lookahead_and_optionally_finish(res_builder)
                    if is_finished:
                        return res
                else:
                    raise Exception("Programming error: undefined kind of string quotation: %s" % quote_type)
            else:
                raise Exception("Programming error: undefined task: %s" % task)
            # increment the position and column
            self.pos += 1
            self.col += 1
        raise JsonParsingException("Programming Error: reached the end of the file, but this should have been noticed earlier, when reaching the self.EOF object.")
    def _unquoted_text_lookahead_and_optionally_finish(self, res_builder):
        """
        Check if the next position is EOF or a character that is invalid for unquoted objects.
        If so, finish up and return the unquoted object.
        """
        next_char = self.chars[self.pos+1]
        if next_char != self.EOF and re.match(self.unquoted_characters, next_char):
            return (False, None)
        # we have encountered a value that is not a valid part of the parser
        # try parsing the result in various ways before returning it
        res = "".join(res_builder)
        # booleans
        if res in ['true', 'True']:
            return (True, True)
        if res in ['false', 'False']:
            return (True, False)
        # null / None
        if res in ['null', 'None']:
            return (True, None)
        # int
        try:
            return (True, int(res))
        except:
            pass
        # float
        error = None
        try:
            flt = float(res)
            if math.isnan(flt) or math.isinf(flt):
                error = "NaN and infinite are not valid JSON values!"
            else:
                return (True, flt)
        except:
            pass
        if error is not None:
            raise JsonParsingException(error)
        # default: string
        return (True, res)


def get_error_message_details(exception=None):
    """
    Get a nicely formatted string for an error message collected with sys.exc_info().
    """
    if exception is None:
        exception = sys.exc_info()
    exc_type, exc_obj, exc_trace = exception
    trace = traceback.extract_tb(exc_trace)
    error_msg = "Traceback is:\n"
    for (file,linenumber,affected,line) in trace:
        error_msg += "\t> Error at function %s\n" % (affected)
        error_msg += "\t  At: %s:%s\n" % (file,linenumber)
        error_msg += "\t  Source: %s\n" % (line)
    error_msg += "%s\n%s" % (exc_type, exc_obj,)
    return error_msg
