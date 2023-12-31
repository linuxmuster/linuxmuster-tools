# Quotas

Utilities functions to get some informations about quota usage for users.

```Console
>>> from linuxmusterTools.quotas import list_user_files
>>> print(list_user_files('kiar')
# Gives an dictionary as output like {
#    'directories': {
#        DIRECTORY_PATH1: {
#            'files': {
#                FILE_PATH1: FILE_SIZE1,
#                FILE_PATH2: FILE_SIZE2,...
#            },
#            'total': DIRECTORY_SIZE
#        },
#        DIRECTORY_PATH2: ...
#    },
#    'total': TOTAL_SIZE,
#}
```
