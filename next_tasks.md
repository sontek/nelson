- We need to clean up the iteration loop a bit.   We want one full iteration to be all the phases completed once.    So for example if we say we want max iterations of
  10, we want each phase in our loop to have ran 10 times unless it identified no additional work was necessary.   This is how the nelson loop is supposed to
  work, basically sending the same prompt multiple times to get it to complete the work.    Our phased approach kind of lost that as it currently just stops when the work
  is complete:   [Pasted text #1 +17 lines]       but we should kick off more iterations from the loop to see if it re-plans it finds more work to do.

- The project should be called nelson not ralph
- update prompt to state don't leave FIXME, TODO, etc. comments but actually do the work.
