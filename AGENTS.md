# ai agents rule for the project

## no code comments

avoid at all costs comments in the codebase, keep the code clean and understandable

## always run lint and test

after any code change, make sure to run both lint and test, even docker builds to make sure the project is ready for production

## try to keep files small

you shouldn't write more than 500 lines of code in one file. if more space is needed, split it into multiple files keeping high readability of the code

for test files it's fine to go over that limit, but not by a huge amount
