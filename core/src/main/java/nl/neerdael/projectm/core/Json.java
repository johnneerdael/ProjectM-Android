package nl.neerdael.projectm.core;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Strict RFC 8259 JSON parser without platform dependencies (org.json is an Android framework class
 * and is stubbed in JVM unit tests). Objects become LinkedHashMap (field order kept), arrays
 * ArrayList, numbers Double, plus String, Boolean and null. Malformed input throws IOException.
 */
final class Json {
    private final String text;
    private int at;

    private Json(String text) { this.text = text; }

    static Object parse(String text) throws IOException {
        Json json = new Json(text);
        json.space();
        Object value = json.value();
        json.space();
        if (json.at != text.length()) throw json.error("trailing characters");
        return value;
    }

    private IOException error(String what) { return new IOException("JSON " + what + " at offset " + at); }

    private void space() {
        while (at < text.length()) {
            char c = text.charAt(at);
            if (c != ' ' && c != '\t' && c != '\n' && c != '\r') return;
            at++;
        }
    }

    private Object value() throws IOException {
        if (at >= text.length()) throw error("unexpected end");
        char c = text.charAt(at);
        switch (c) {
            case '{': return object();
            case '[': return array();
            case '"': return string();
            case 't': return literal("true", Boolean.TRUE);
            case 'f': return literal("false", Boolean.FALSE);
            case 'n': return literal("null", null);
            default:
                if (c == '-' || (c >= '0' && c <= '9')) return number();
                throw error("unexpected character");
        }
    }

    private Object literal(String word, Object value) throws IOException {
        if (!text.startsWith(word, at)) throw error("bad literal");
        at += word.length();
        return value;
    }

    private Map<String, Object> object() throws IOException {
        Map<String, Object> map = new LinkedHashMap<>();
        at++;
        space();
        if (at < text.length() && text.charAt(at) == '}') { at++; return map; }
        while (true) {
            space();
            if (at >= text.length() || text.charAt(at) != '"') throw error("expected a field name");
            String key = string();
            space();
            if (at >= text.length() || text.charAt(at) != ':') throw error("expected ':'");
            at++;
            space();
            map.put(key, value());
            space();
            if (at >= text.length()) throw error("unexpected end");
            char c = text.charAt(at++);
            if (c == '}') return map;
            if (c != ',') throw error("expected ',' or '}'");
        }
    }

    private List<Object> array() throws IOException {
        List<Object> list = new ArrayList<>();
        at++;
        space();
        if (at < text.length() && text.charAt(at) == ']') { at++; return list; }
        while (true) {
            space();
            list.add(value());
            space();
            if (at >= text.length()) throw error("unexpected end");
            char c = text.charAt(at++);
            if (c == ']') return list;
            if (c != ',') throw error("expected ',' or ']'");
        }
    }

    private String string() throws IOException {
        StringBuilder out = new StringBuilder();
        at++;
        while (true) {
            if (at >= text.length()) throw error("unterminated string");
            char c = text.charAt(at++);
            if (c == '"') return out.toString();
            if (c < 0x20) throw error("control character in string");
            if (c != '\\') { out.append(c); continue; }
            if (at >= text.length()) throw error("unterminated escape");
            char e = text.charAt(at++);
            switch (e) {
                case '"': case '\\': case '/': out.append(e); break;
                case 'b': out.append('\b'); break;
                case 'f': out.append('\f'); break;
                case 'n': out.append('\n'); break;
                case 'r': out.append('\r'); break;
                case 't': out.append('\t'); break;
                case 'u':
                    if (at + 4 > text.length()) throw error("short unicode escape");
                    try {
                        out.append((char) Integer.parseInt(text.substring(at, at + 4), 16));
                    } catch (NumberFormatException bad) {
                        throw error("bad unicode escape");
                    }
                    at += 4;
                    break;
                default: throw error("bad escape");
            }
        }
    }

    private Double number() throws IOException {
        int start = at;
        if (text.charAt(at) == '-') at++;
        if (at >= text.length()) throw error("bad number");
        if (text.charAt(at) == '0') at++;
        else if (!digits()) throw error("bad number");
        if (at < text.length() && text.charAt(at) == '.') { at++; if (!digits()) throw error("bad fraction"); }
        if (at < text.length() && (text.charAt(at) == 'e' || text.charAt(at) == 'E')) {
            at++;
            if (at < text.length() && (text.charAt(at) == '+' || text.charAt(at) == '-')) at++;
            if (!digits()) throw error("bad exponent");
        }
        return Double.valueOf(text.substring(start, at));
    }

    private boolean digits() {
        int start = at;
        while (at < text.length() && text.charAt(at) >= '0' && text.charAt(at) <= '9') at++;
        return at > start;
    }
}
