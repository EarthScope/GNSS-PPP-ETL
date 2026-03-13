base_dir/
│
├── static/
│   ├── atx/
│   ├── ocean/
│   ├── atmosphere/
│   └── tables/
│
├── products/
│   └── year/
│       └── doy/
│           └── common/
|
│
├── rinex/
│   └── year/
│       └── doy/
│


**goal 1:

Given a FileQuery object, use the instance attributes format, content, and date to determine where the file goes and where it can be found.

We'd lkely need some sort of "protocol" that takes in these combinations and the query date
