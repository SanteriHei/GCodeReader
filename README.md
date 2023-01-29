# Simplified GCode reader
The cnc.py file contains an extremely limited and simple parser for GCode, and 
a simple sceleton for executing the commands.

## Usage
The implementation doens't contain any dependencies, but Python version 3.6+
is required. One can then test the program by running 
```python
python cnc.py rectangle.gcode
```

## Notes
- The design of the reader is quite simple: 
   - Avoid deeply nested if-else structures by using simple "dispatcher" based
   on the gcode.
   - Each function that executes a gcode(s) is passed the gcode, current line 
   number, and possible extra arguments that are parsed from the line
   - Create readable error messages, provide the user context (i.e. line number), so that the errors are easy to locate and fix.
   - Doesn't implement all the GCodes due to time constraints, but technically
   implementing new codes is quite easy.
