## The Edit section

The edit section introduces small changes to files in the test folder,
with a variety of pre-implemented/easy-to-construct edit commands.
Edits are reverted every time a test is run, except if marked with a star `*`:

    edit<*> (filename.ext): # Example edit section.
         ^
         |______: Make the changes persistent accross subsequent tests.

### Introduction

#### DIFF

`DIFF` is the most basic instruction to transforms lines.
For example, to transform one arithmetic operation within the file:

    DIFF a = b + c
    ~    a = b - (c * d)

More generally:

```
DIFF  This line is matched in the file irrespective of indentation.
~     And replaced by *this* line. Trailing whitespace is ignored for matching.
```

Quote the lines to disambiguate parsing or trailing space.


```
DIFF "~~This line is matched disregarding indentation, but not trailing space: "
~    "~~The replaced line is not trimmed for trailing space either: .  .  .  "
```

#### INSERT and REMOVE

New lines are created with `INSERT` (`INSERT BELOW` or `INSERT ABOVE`).
For example:


```
INSERT  This line is matched, then the lines ↓ below are inserted after it.
     +  This new line is inserted within the file.
     +  This new line as well.

INSERT +  These two lines are inserted within the file.
       +  Right before the match below ↓.
          This line is matched and pushed down by the above 2 new lines.
```

The reverse operation is `REMOVE`. For example:


```
REMOVE  This line is matched and removed from the file.
```

#### REPLACE

For more sophisticated, file-wise edits, use `REPLACE` instruction.

```
REPLACE     \bword\b BY Woord   # Use python regex syntax to replace first match.
REPLACE ALL \bword\b BY Woord   # Replace all occurences in file.
```

Disambiguating is possible with two-liners (also eases reading).

```
REPLACE DOWN (BY THE RIVERSIDE)
BY      DROWN \1 # Comments not included in the pattern.
```

To disambiguate more, use quoted strings.

```
REPLACE "GOODBYE" BY "# <3 BYEBYE <3 #"
```

Long patterns can be split over multiple lines continuated by a `/` symbol.
Successive lines are concatenated together into the final patterns.

```
REPLACE long (pattern|line)\s+
/       split (a(?:c){2}ro(?:s){2}) 2 lines
BY      Replacing \1 by..
/       .. this replacing \1 split \2 two lines as well.
```

#### PREFIX and UNPREF

For simple `DIFF` operations
that would otherwise be ambiguous to parse or tedious to write correctly,
use `PREFIX` and `UNPREF` instructions.
For example:

```
PREFIX  (#) This line is matched then commented out in the file.
PREFIX  (4) This line is matched then indented by 4 spaces.
UNPREF  (4) This line dedented by 4 spaces.
PREFIX  (4, 8) If this line was *exactly* indented by 4 spaces, indent it by 4 more.
PREFIX  (2t, #) Comment out this line only if it was indented by exactly 2 tabs.
PREFIX/ (r'(\s*)#(\s*)', \1--\2) Change '#' comment sign by '--', keeping blanks.
```

Prefix notations are either :
- a raw (stripped) read without quotes                (eg. above: `\1--\2`)
- a quoted python-like string to disambiguate parsing (eg. `r'(\s*)#(\s*)'`)

Then:
- If the `/` mark is given, notations are interpreted as exact python regexes.

- Otherwise, if digits appear within the notation,
  then it is interpreted as a *condensed* notation where:
  - numbers repeat the following character
    (eg. `4#`   means `"####"`)
  - `t` means tab
    (eg. `2t#t` means `"\t\t#\t"`)
  - `s` means space, and may be elided in last position
    (eg. `4s#1` means `'    # '`)

 - In neither of the above two cases, the notation is interpreted literally.


### The line model

Other instructions also accept prefix specifications. For instance:

```
DIFF (4) This line is only matched if exactly indented by 4 spaces.
~    (8) The replacing line is indented by exactly 8 spaces.

INSERT (4)      This line is only matched if it is exactly indented by 4 spaces.
     + ('4s# ') The new line has same indentation but is commented out.
```

Interactions between prefixing options can get sophisticated.
To understand how they work, here is the internal model of a matched line:

                    __________________" a line "_______________
    (not in "line") |   I        P        <X>     A or B   T   | (not in "line")
    (SOL='\n' or ^) |(indent) (prefix) <(extra)> (body) (tail)| (EOL='\n' or $)

With:
- `indent (I)`: Variable size leading whitespace (think of it as `\s*`).
- `prefix (P)`: As specified by user with a prefix notation (eg. `4#1` or nothing).
- `extra  (X)`: New characters to insert, specified by user with a prefix notation.
- `body (A|B)`: Actual line content, specified with raw reads or quoted strings.
- `tail   (T)`: Variable size trailing space (`\s*`), ignored if body is a raw read.

For example, the following instruction:

    UNPREF (#1) a = b + c

Matches the following line:

    line = "\t\t# a = b + c  "
            I·I·PPAAAAAAAAATT
           '\t\t'--------------: indent (kept)
               '# '------------: prefix (removed by the instruction)
                 'a = b + c'---: body   (kept)
                          '  '-: tail   (ignored by the instruction)

Notice That the `prefix` takes precedence over the indent,
and that an exact, non-empty `tail` can requested with quoting. For instance:

    UNPREF (t#1) "a = b + c  "

Matches the same line, but differently:

    line = "\t\t# a = b + c  "
            I·P·PPAAAAAAAAATT
           '\t'----------------: indent (now reduced)
             '\t# '------------: prefix (removed by the instruction)
                 'a = b + c'---: body   (kept)
                          '  '-: tail   (now mandatory for the match)

To match an empty tail exactly,
quote the line body and mark it with a `*`:

    UNPREF (t#1) "a = b + c" *

The above instruction would not match the example line again
because it ends with two spaces.

### Full specifications

With the above model in mind, here are full forms
for all prefix-aware instructions.

#### Single-line instructions

```
PREFIX</|*> <ALL> (<prefix,> extra) Body of the line to prefix (A).
       ^ ^   ^^^    ^^^^^^   ^^^^^
       | |    |        |       |__: Insert before body (X).
       | |    |        |__________: Must match if specified (P).
       | |    |___________________: Don't stop after first match.
       | |________________________: Toggle variable indent (I) before prefix/body.
       |__________________________: Interpret as regex (pat, sub) instead of (P, X).

UNPREF</|*> <ALL> (prefix) Body of the line whose prefix to strip (A).
       ^ ^   ^^^   ^^^^^^
       | |    |        |__: Matched and removed (P).
       | |    |___________: Don't stop after first match.
       | |________________: Toggle variable indent (I) before prefix.
       |__________________: Interpret prefix as an exact regex to match and remove.

REMOVE</|*> <ALL> <(prefix)> Body of the line to remove (A).
       ^ ^   ^^^    ^^^^^^
       | |    |         |__: Must match if specified (P).
       | |    |____________: Don't stop after first match.
       | |_________________: Toggle variable indent (I) before prefix/body.
       |___________________: Interpret prefix as an exact regex to match and remove.
```

The variable indentation (`I`) is matched or not depending on `*` symbol.
The switch is crafted in a way that `*` is not required for most natural edits.
More precisely:

```
PREFIX     (X) Insert extra prefix.        ( IA →  IXA)
PREFIX*    (X) .. only if not indented.    (  A →   XA)
PREFIX  (P, X) Insert extra prefix.        ( PA →  PXA)
PREFIX* (P, X) .. with flexible indent.    (IPA → IPXA)

UNPREF  (P) Remove prefix.                 (IPA →   IA)
UNPREF* (P) .. only if exact match.        ( PA →    A)

REMOVE      Remove regardless of indent.   ( IA →  ∅  )
REMOVE*     Remove with exactly no indent. (  A →  ∅  )
REMOVE  (P) Remove on exact prefix match.  ( PA →  ∅  )
REMOVE* (P) Remove on loose prefix match.  (IPA →  ∅  )
```

For instance:

```
PREFIX  (#)    Comment out irrespective of indentation.
PREFIX  (4)    Indent this line by 4 more spaces.
PREFIX  (8, 4) Dedent by 4 space if it was exactly indented by 8 spaces.
PREFIX  (8, #) Comment out if exactly 8 spaces.
PREFIX* (#)    Comment out if there was no indent.
PREFIX* (8, 4) Indent by 4 if indent was at least 8.

UNPREF  (#1) Remove '# ' prefix irrespective of indentation.
UNPREF  (#)  Uncomment if there was no space after '#'.
UNPREF  (4)  Dedent by 4, provided there were at least 4.
UNPREF* (4)  Remove all indentation, provided it was exactly 4.

REMOVE  (4) Remove if indentation is exactly 4.
REMOVE* (4) Remove if indentation is at least 4.
```

If more power is required, take manual control with regexes.

```
PREFIX/ (\s*#\s*, '')         Flexible uncomment + dedent.
PREFIX/ (r'\s*(-)\s*', \1{2}) Dedent if introduced with '-', now '--' instead.
UNPREF/ (\s*#+)               Uncomment + dedent, robust to multiple '#' signs.
UNPREF/ (r'(\s*)#+')          First group is *kept* so this only removes '#' signs.
PREFIX/ (r'(\s*)#+', \1)      Equivalent to the above.
REMOVE/ ALL (\s*##+)          Remove all lines with more than 1 '#' comment sign.
```

#### Paired lines instructions


`DIFF` and `INSERT` provide identic options, yet with different syntaxes.

```
                   __________: Toggle variable indent (I) before prefix/body (A).
                  |        __: Must match if specified (P).
                  |       |
                  v    vvvvvv
DIFF</> <ALL>    <*> <(prefix)> Body of the line to match.    (A)
   ~ ^   ^^^  <**|*>  <(extra)> Body of the replacement line. (B)
     |    |    ^^^^     ^^^^^
     |    |     |        |___: Insert before body (X).
     |    |     |____________: Toggle kept part (I/IP) before body (B).
     |    |__________________: Don't stop after first match.
     |_______________________: Interpret (prefix, extra) as (pattern, substitution).


INSERT <BELOW></> <ALL>    <*>  <(prefix)> Body of the line to match.   (A)
     +                  <**|*>  <(extra1)> Body of the line to insert. (B1)
     +                  <**|*>  <(extra2)> Body of the line to insert. (B2)
     ...                 ...               ...


INSERT <ABOVE></> +     <**|*>  <(extra1)> Body of the line to insert. (B1)
                  +     <**|*>  <(extra2)> Body of the line to insert. (B2)
                  ...    ...               ...
                  <ALL>    <*>  <(prefix)> Body of the line to match.   (A)
```

The variable indentation (`I`)
is matched or not depending on the *match* `*` symbol.
The part kept (`I/IP`) in the new line, before the body (`B`),
depends on the *replace* `*` or `**` symbol.
The switch are crafted in a way that `*` or `**` are not required
for most natural edits. More precisely:

    INSERT        Match any indent.      (  IA)
         +        Keep it.               (  IB)
         + *      Drop it.               (   B)
         +    (X) Extend it.             ( IXB)
         + *  (X) Change it.             (  XB)

    INSERT    (P) Match exact prefix.    (  PA)
         +        Keep it.               (  PB)
         + *      Drop it.               (   B)
         +    (X) Change it.             (  XB)
         + *  (X) Extend it.             ( PXB)

    INSERT *      Match without indent.  (   A)
         +        Keep it.               (   B)
         +    (X) Extend it.             (  XB)

    INSERT *  (P) Match prefix + indent. ( IPA)
         +        Keep it.               ( IPB)
         + *      Drop it.               (  IB)
         + **     Drop them.             (   B)
         +    (X) Change it.             ( IXB)
         + *  (X) Extend it.             (IPXB)
         + ** (X) Change them.           (  XB)

The same holds for `INSERT ABOVE` and `DIFF`.
