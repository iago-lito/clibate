The intent: a general-purpose framework to test a CLI project needing numerous
input files, and where all tests are only small variations upon a set of base
input files.

On the one side: a folder with the set of base input files.  
On the other side: a folder with tests specification files.  

In every spec file, a sequence of numerous tests are listed in the dedicated
testing language. Chunks in spec files define the base input files to work with,
the CLI command to run, the slight modifications to be patched against the
setup, and the output expectations.

When run, every test gets a temporary folder with a copy of all the base input
files, and successively applies the patches / run the command / compare actual
*vs.* expected outputs to eventually gather all tests results.
