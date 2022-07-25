# Clibate

There is this command-line program
that you would like to write automated tests for, but:
- you don't have the sources, or
- they are monstrous(ly untested) with no ready-to-use testing framework, or
- you are not sure in which language they are/were written, or
- you want your tests to be integrative, or
- you want your tests to not rely on implementation details..

anyway the sources are black-boxed.  
Moreover, your program feeds on one or several input data files,
and its output fine-grainedly depends
on numerous subtle details of the input files.

To test that, you would not only need to construct mock input files
and feed your command with them to compare against your expectations,
you would also need to construct *numerous* replicates of mock input files,
changing one slight detail every time,
and checking how it changes the program output and whether this matches
your expectations.

Well, clibate is meant to do exactly that.
It automates the setting of a mock set of data files,
and the repeated introduction of permanent or temporary changes to it.
This happens within a dedicated `.clib` file specifying the tests to be run.

Here is what a clibate specification file looks like:

```clib
# Setup a blackboxed command you'd like to test (here a dummy example with awk).
command: cat input_file.csv | awk -f main.awk

# Bring data from your input folder into the temporary testing environment.
copy: dummy_data -> input_file.csv
# (or create it right here)
file (input_file.csv):: EOD
    A 5
    B 8
    C 13
EOD

# Create another file in the testing environment (here a dummy awk program).
file (main.awk):: EOF
  {
    sum += $2
    if (chain == "") {
      chain = $1
    } else {
      chain = chain "-" $1
    }
  }
  END {
    print chain ": " sum
  }
EOF

# Setup expectations and run your first integrated test.
success: The program is running correctly.
    A-B-C: 26
# That's a first test.

# Now introduce a modification into the input file, and expect different output.
test: The difference is written on disk and reflected into the program output.
edit (input_file.csv):
    DIFF   B 8
       ~   BB 88
success:
    A-BB-C: 106   # That's a second test.

# Modifications are temporary and the files are reset after every test..
success: The program is running like the first time.
    A-B-C: 26     # third test..

# .. unless explicitly required, here with the '*' symbol after 'edit'.
test: Introduce permanent modifications to the awk program file.
edit* (main.awk):
   DIFF 'chain = chain "-" $1' # Disambiguate parsing with python-style strings.
   ~    'chain = chain "+" $1'
success:
    A+B+C: 26     # fourth test, etc.

success: The modification is now persistent accross tests.
    A+B+C: 26

# Expect errors on the program output if you introduce mistakes in the sources.
test: Failing with invalid awk syntax.
edit (main.awk):
    DIFF  END {
    ~     END {{
failure (1): # Expect error code 1, and the following message on stderr.
    awk: main.awk:11: (END OF FILE) # Yeah, because there is unmatched '}' now.

# The 'edit' section offers other various kinds of instructions.
test: Transform awk sources.
edit (main.awk):

    INSERT ABOVE + BEGIN {
                 + '    printf ">>"'
                 + }
                   { # <- This matches the first line in file.

    INSERT 'chain = chain "+" $1'
         +  chain = chain $1     # <- Insert new behaviour.

    REPLACE (:)\s BY \1\1\t      # <- Use python regex patterns.

success:
    >>A+BB+CC::	26

test: Comment out a line in awk sources.
edit (main.awk):
    PREFIX (#) sum += $2
success:   A+B+C:

test: Delete a line in awk sources.
edit (main.awk):
    REMOVE 'chain = chain "+" $1'
success:    A: 26

test: Alternately, modify the command.
command: cat input_file.csv | awk -f main.awk | sed 's/: / is /'
success: A+B+C is 26

# Writing integrated tests for CLI programs has barely been this easy, right?
```

Run all the above tests in as single line with:

```sh
$ ./main.py ./tests/specs.clib -i ./tests/input_folder
Check basic behaviour of clibate with awk command (./tests/specs.clib):
  The program is running correctly.. PASS
  The difference is written on disk and reflected into the program output.. PASS
  The program is running like the first time.. PASS
  Introduce permanent modifications to the awk program file.. PASS
  The modification is now persistent accross tests.. PASS
  Failing with invalid awk syntax.. PASS
  Transform awk sources.. PASS
  Comment out a line in awk sources.. PASS
  Delete a line in awk sources.. PASS
  Alternately, modify the command.. PASS

✔ Success: 10 tests run.
```

Clibate tests specification files can include each other with the `include:`
section to organize your tests in a structured way.

Thourough documentation regarding the various supported sections
(`success:`, `failure:`, `test:`, `edit:`, `file:`, `command`,
`stdout:`, `stderr:`, *etc.*)
is to be written yet.
Meanwhile, there is documentation under the form of python docstrings
throughout the source scripts.

The clib spec files parser is also designed in a modular way
that makes it possible to extend it with user-defined sections
like `compile-project:` or `verify-matrix-symmetry-on-stdout:`.
To this end, subclass the `Reader` and `Actor` types (framework pattern)
and feed them into the parser.
Documentation regarding user-defined parser extensions is still to be written,
and the API stabilized,
but examples can be found under the sources `./sections/` folder.

Happy testing!
