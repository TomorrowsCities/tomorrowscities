---
title: App Engine
emoji: 🦀
colorFrom: indigo
colorTo: pink
sdk: docker
pinned: false
---

## What is New?

### Excel support:
You can  upload Excel files containing your tabular data such as individual, household, fragility or vulnerability data. However, processing excel files is very slower than processing JSON files so I definitely suggest working with JSON files. You can convert your Excel files via panda framework. The platform also does not try to convert the coordinates even if there is any in the Excel file because there is no way to know which columns represent the coordinates or coordinate reference systems without metadata. So Excel spreadsheets should be used to provide non-geo related tabular data.  So please use them only for data not containing any geo-specific information. 

### Dar Es Salaam Study
[Sample Dataset](https://drive.google.com/file/d/1BGPZQ2IKJHY9ExOCCHcNNrCTioYZ8D1y/view?usp=sharing) now contains some visioning scenario for Dar Es Salaam case.
