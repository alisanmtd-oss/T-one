!macro customInstall
  CreateShortCut "$SMPROGRAMS\T One CLI.lnk" "$INSTDIR\resources\T-One-CLI.cmd"
!macroend

!macro customUnInstall
  Delete "$SMPROGRAMS\T One CLI.lnk"
!macroend
