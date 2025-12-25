# fried_git_tools
git scripts to solve real engineering problems. Such as tool to push a large amount that will trigger [unpacker error]



## git_sync_to_remote.sh

### usage

* This script pushes git commits in batches to avoid server limits

    such as pack size limits or timeout issues when pushing many commits. 

    If you encounter errors like **[unpacker error]**, this is the right tool.

* Make sure you have setup your git folder and **ready to push**

    You may also create the branch at your server at first to avoid unnecessary error. 

* Usage: `./git_sync_to_remote.sh <workspace_directory> [remote] [branch]`

    You can review detail message on the top of the sh

* **FORCE_PUSH is set to true by default**, make sure you **don't get the branch wrong**

### detail

* Like you want to mirror unreal 5.4 branch into your own git, you can use this tool

    * you can firstly download the 5.4 branch into a folder

        ```sh
        git init --bare
        git remote add origin <SOURCE_REPO_URL>
        git config remote.origin.fetch "+refs/heads/5.4:refs/heads/5.4"
        # adds develop to the fetch list
        #git config remote.origin.fetch "+refs/heads/master:refs/heads/master"
        ```

    * then add a remote like "destination"

        `git remote add destination <DESTINATION_REPO_URL>`

    * If you do this, you are likely to sync unreal 5.4 to your own git

        `git push destination +5.4:5.4`

        But you are likely to be limited by the server, and yield: `[unpacker error]`

    * Then you call

        `./git_sync_to_remote.sh <workspace_directory> destination 5.4`

        It will split the commit and push to your git

