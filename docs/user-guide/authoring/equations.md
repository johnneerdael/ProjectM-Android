# Equations

Preset equations are written in MilkDrop's expression language. MilkDrop 2 runs them with NS-EEL2, which compiles to x86 code. projectM runs them with projectm-eval, a portable reimplementation. The syntax is the same, but the two do not always handle edge cases the same way, and real presets depend on those edge cases.

All values are 64-bit floating point. Names are case-insensitive. An unknown name is created on first use with value 0. A typo therefore never causes an error: it silently creates a new variable that stays zero.

## Where the two evaluators agree

| Feature | Behaviour |
|---|---|
| `equal(a,b)`, `==`, `!=` | Equal when \|a−b\| < 0.00001 |
| `above`, `below`, `<`, `>`, `<=`, `>=` | Exact comparison |
| `!x`, `bnot(x)` | 1 when \|x\| < 0.00001 |
| `band`, `bor` | Logical, with the same 0.00001 tolerance; both arguments are evaluated |
| `&&`, `\|\|` | Logical, short-circuit |
| `&`, `\|` | Bitwise on integers |
| `sqrt(x)` | `sqrt(abs(x))`: never NaN |
| `sigmoid(x,c)` | 1/(1+e^(−x·c)) |
| `loop(n, …)`, `while(…)` | Capped at 1,048,576 iterations |
| `exec2`, `exec3` | Evaluate in sequence, return the last |
| `megabuf(i)`, `gmegabuf(i)` | 128 blocks × 65,536 entries; `buf[i]` reads `megabuf(buf+i)`, `gmem[i]` reads `gmegabuf(i)` |
| Assignment | `= += -= *= /= %= \|= &= ^=` |
| `int(x)` | Floor |

## Where they differ

| Case | MilkDrop 2 (NS-EEL2) | projectM (projectm-eval) |
|---|---|---|
| `x / 0` | ±infinity or NaN | **0** (when \|divisor\| < 0.00001) |
| `a % b` | Absolute values of both operands, then integer remainder; 0 if `b` is 0 | C signed remainder: `-5 % 3` is −2, not 2; 0 if `b` is 0 |
| `pow(negative, fraction)` | NaN | 0 |
| `log(x)`, `log10(x)` for x ≤ 0 | NaN or −infinity | 0 |
| `asin`, `acos` outside −1…1 | NaN | 0 |
| `if(c, a, b)`, `c ? a : b` | False when \|c\| < 0.00001 | False only when c is exactly 0 |
| `reg00`–`reg99`, `gmegabuf` | Process-global | Per preset |
| Lone `.` | 0 | Syntax error (ProjectM TV accepts it as 0) |
| `$pi`, `$e`, `$phi`, `$x1F`, `$'a'` | Not available | Available |

projectm-eval turns most domain errors into 0, where NS-EEL produces infinity or NaN. A preset can therefore look fine in projectM while propagating NaN in MilkDrop, and the other way round. The unsafe values matter most once they reach the GPU, as warp coordinates or shader inputs: see [what cannot be predicted](testing.md#what-source-analysis-cannot-settle).

## `rand()` is not an integer

```ini
per_frame_init_1=choice=rand(4);
```

In MilkDrop 2's release build, `rand(n)` returns a floating-point value from 0 up to `floor(n)`. The integer form exists only in an EEL1 compatibility mode, which the release build does not enable. projectm-eval matches the release build. For an index, write:

```ini
per_frame_init_1=choice=int(rand(4));
```

Both evaluators use a Mersenne Twister with the same fixed seed, so the *sequence* of `rand()` values is deterministic from program start. Which values your preset gets depends on everything that called `rand()` before it.

## Patterns that work everywhere

**Envelope follower with attack and decay**

```ini
per_frame_1=kick=max(.78*kick,min(1.5,max(0,(bass-.95)*1.6)));
per_frame_2=env=.92*env+.08*min(2,max(0,bass_att));
```

`kick` jumps up on a bass hit and decays by 22% per frame. `env` is a slow average.

**Beat detection with a refractory period**

```ini
per_frame_1=beat=above(bass,1.3)*above(time,last+0.25);
per_frame_2=last=if(beat,time,last);
```

**Guarded division and power**

```ini
per_frame_1=ratio=a/max(abs(b),0.001)*sign(b);
per_frame_2=curve=pow(max(x,0.000001),2.2);
```

The two engines disagree on what a division by zero produces, so don't rely on getting 0 or infinity.

**Counting through a cycle**

```ini
per_frame_1=step=(step+above(bass,1.2))%4;
```

`step` stays within 0…3 in both engines, because it never goes negative.

## Implicit precision

- Equations are evaluated in double precision. Settings, shader uniforms and the warp rotation are narrowed to 32-bit float before use.
- Float literals in shaders are 32-bit. In ProjectM TV they reach the GPU with full float32 precision.
- The host's number locale can affect how preset files are parsed in some projectM builds. ProjectM TV never changes the locale.
