pyeverything
============

Read the db file of [everything](http://www.voidtools.com/)

Command line usage
------------------

```
usage: everything_db.py [-h] [-f FOLDER] [-c CONTENT] file_pattern

positional arguments:
  file_pattern          filename

optional arguments:
  -h, --help            show this help message and exit
  -f FOLDER, --folder FOLDER
                        folder pattern
  -c CONTENT, --content CONTENT
                        content pattern
```

For example, to search every python file that contains `print` and with `project` in the full path name:

`everything_db.py *.py -f project -c print`

As python module
----------------

Open everything database by `open_everything()` and then call `find_all()` method, `method` argument has three opitions for file name matching:

* `find`: use `string.find()` 
* `fnmatch`: use `fnmatch`
* `re`: use `re`

```
from everythin_db import open_everthing

db = open_everything()
for fullpath in db.find_all("*.py", method="fnmatch"):
    print(fullpath)
```
