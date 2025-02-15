
# Information pertaining to transcoding 4k media format on plex

**NOTE: for 2022 – Plex has come a long way since this FAQ was originally written, HW transcoding has become more available and more stable, and tone mapping was recently added to address the hdr/sdr color conversion issues.**

The first 4 ‘rules’ generally are no longer as important as they once were, but may still be a good thing to bear in mind.

Dolby Vision, is an entirely other mess. THIS thread/FAQ is NOT about DV.

DV work is still in progress, and there are no perfect TV’s or external devices. There are multiple other threads on dolby vision, I would recommend everyone check the links near the bottom of the first post, or search the forum for their particular tv + dolby vision (ie dolby vision sony) to find relevant threads and posts concerning their issues.

Adding your tv/device model# to a search will probably help narrow it down even further.

___

*** TONE MAPPING SUPPORT ADDED @ [https://support.plex.tv/articles/hdr-to-sdr-tone-mapping/](https://support.plex.tv/articles/hdr-to-sdr-tone-mapping/) ***  
do note: enabling tone mapping potentially can cause your server to no longer be able to transcode 4k due to the extra load, especially on windows (only cpu currently supported).

___

TLDR; buy a Shield _PRO_ or [XBOX ONE](https://forums.plex.tv/t/plex-for-xbox/85265/95) > 4K/atmos receiver > 4K tv

added 11/2023: Recent models of Amazon FireTV devices may have support for bitstream/passthrough.

No, nothing new has changed above.

_shield pro is recommended over shield tube, due to the tube having less ram and ongoing troubles with high bit rate 4k bluray remuxes. if/when those issues are resolved, then this recommendation will be amended._

Note for 2022: shield experience update has added a new feature, per @ [\[INFO\] Plex, 4k, transcoding, and you - aka the rules of 4k - #446 by W0lfm0n](https://forums.plex.tv/t/info-plex-4k-transcoding-and-you-aka-the-rules-of-4k/378203/446) there may be hope for tube owners. I still recommend the pro, do not try to save a few dollars when it affects the whole 4k experience.

___

“I just want my 4K+ATMOS to work” > [Diskstation/Roku/AppleTV Best Setup - Advice Please - #6 by FordGuy61](https://forums.plex.tv/t/diskstation-roku-appletv-best-setup-advice-please/614400/6)

___

added 11/2023: Another great HD audio reference explainer @ [Reddit - Dive into anything](https://www.reddit.com/r/appletv/comments/kdkz6a/understanding_audio_and_apple_tv_atmos_samsung/)

___

_These rules are a guideline and meant to be humorous while still being informative and accurate as possible_

## [](https://forums.plex.tv/t/info-plex-4k-transcoding-and-you-aka-the-rules-of-4k/378203#the-ruleshttpsenwikipediaorgwikifight_club-of-4k-and-plex-1)[The Rules](https://en.wikipedia.org/wiki/Fight_Club) of 4k and plex

-   The first rule of 4k is
    -   Don’t bother transcoding 4k
-   The second rule of 4k is
    -   **DON’T** bother transcoding 4k
-   The third rule of 4k is
    -   If you cannot direct play 4k, then perhaps you should not even be collecting 4k.
-   The forth rule of 4k is
    -   If you don’t have the storage space for a copy of both 4k and 1080/720, then perhaps you should not even be collecting 4k.
-   The fifth rule of 4k is
    -   To direct play 4k, your entire playback chain must be compatible with both the VIDEO and AUDIO codecs of the content you are trying to play.
    -   4k bluray ripped content typically includes HD audio (ie lossless truehd/atmos), which must have a compatible audio player (ie a truehd/atmos compatible receiver)
    -   DTS-HD MA should always have a lossy core which should direct play, even if your system does not support the HD part. Some TV’s and/or soundbars do not support any DTS.
    -   This may still depend on what the player reports as compatible back to the plex server, as the server will transcode or not, accordingly.
-   The sixth rule of 4k is
    -   You cannot direct play HD audio via optical or ARC, instead you must use use a compatible lossy audio stream such as dolbydigital/dts 5.1 or stereo. You can either manually remove the HD audio streams (ie remux), or choose a non-hd audio stream from within plex pre-play screen or pause screen options.
    -   The DTS core (as explained above), should be able to direct play over ARC and optical, assuming your device(s) support DTS (not all do).
    -   about atmos [The ultimate guide to Dolby Atmos: what it is and how to get the best possible sound | Digital Trends](https://www.digitaltrends.com/home-theater/dolby-atmos-sound/)
-   The seventh rule of 4k is
    -   You must use cables that are compatible with hdmi 2.0 or higher. (Premium High Speed/Ultra High Speed) See @ [HDMI - Wikipedia](https://en.wikipedia.org/wiki/HDMI#Cables) for details.
    -   Your equipment may need to be manually configured for hdmi 2.0+ (some are set to hdmi 1.4 by default for compatibility).
-   The eighth and non-final rule of 4k is
    -   Generally you will need gbit ethernet because 4k bitrate bursts can exceed 100mbit. smart tv’s often have 100mbit which can cause buffering on otherwise direct playing content.
        -   Wifi can work, but entirely depends on your network and how much other wifi interference in range. You should not expect consistent 4k playback over wireless even if it works most of the time.
        -   reddit thread about 4k/hevc peak bandwidth usage [Reddit - Dive into anything](https://www.reddit.com/r/PleX/comments/eoa03e/psa_100_mbps_is_not_enough_to_direct_play_4k/)

___

-   The simplest 4k direct play plex solution is nvidia shield + 4k/atmos receiver + 4k hdr tv.
-   If you are direct playing 4k, then you do NOT need a hugely powerful server, you just need fast enough disk and network.
-   To avoid transcoding for remote and non-4k clients, keep your 4k content in separate plex libraries. (and don’t give users who can’t direct play 4k access to them)
-   This may of course mean that you keep a 4k copy and a 1080/720 copy, but if you are collecting 4k content then you should not be worried about storage space, should you?
-   if you don’t want to create a separate library, you can use LABELS to restrict your users from seeing 4k content:  
    ![image](https://global.discourse-cdn.com/plex/original/3X/3/a/3ab1bb4dd22a571b7ccfc7fae2324af52bbe09e6.png)  
    

___

## [](https://forums.plex.tv/t/info-plex-4k-transcoding-and-you-aka-the-rules-of-4k/378203#subtitles-2)Subtitles

Depending on the client and subtitle type, enabling subtitles may cause video transcoding. Since plex does not transcode INTO x265, your 4k video will be transcoded down to x264 SDR, and you will lose all the benefits of 4k hdr.

So if you are having problems with transcoding what you think should be direct play, then double check if you have subtitles enabled, then disable them and see if it works.

In order to direct play subtitles, your CLIENT must be able to direct play those subtitles.

Client capabilities vary greatly, some clients may always require transcoding to have subtitles. Other clients may handle most subtitle types.

For example, Nvidia shield can direct play 4k with most subtitles types, like SRT and PGS.

___

## [](https://forums.plex.tv/t/info-plex-4k-transcoding-and-you-aka-the-rules-of-4k/378203#plex-and-4k-transcoding-3)Plex and 4k transcoding

Ok I want to ignore all the above and still want to transcode 4k; There is no free lunch. If you are transcoding 4k instead of having a direct play solution, then you will pay for it instead with expensive server hardware.

1080 transcoding is like a grain of sand on the beach of 4k transcoding. that is how much more power 4k requires. Great power does not come cheaply or easily.

transcoding 4k with CPU requires an extremely powerful cpu ([plex cpu support article](https://support.plex.tv/articles/201774043-what-kind-of-cpu-do-i-need-for-my-server/?_ga=2.6591858.1958264652.1560178819-668607207.1553270397))

transcoding 4k with GPU requires active plex pass

audio is never transcoded on GPU so the cpu must be powerful enough to handle the number of streams expected even when GPU is doing the video.

plex does not currently transcode TO x265

any transcoding is also a highly IO intensive operation, this means you need sufficient ram, disk IO, and network bandwidth to get this bits in, converted, and sent out to the client(s).

plex does not currently do color mapping or conversion from HDR to SDR. transcoded HDR will have washed out colors.

-   tone mapping at the transcoder added @ [Plex Media Server - #381 by StSimm1](https://forums.plex.tv/t/plex-media-server/30447/381)
-   some clients can now color correct the washed out colors and display hdr on an sdr display (experimental ios/android players I believe). The server is NOT doing it, the client/player is.

transcoding 4k hdr without a separate gpu requires a 7th generation intel cpu (i3/5/7 7000 series) with a 6th generation quicksync capable igpu. (ie intel uhd 600 series or better)

intel igpu transcoding is fully supported on both windows and linux

nvidia gpu transcoding is fully supported on windows.

nvidia linux gpu transcoding currently only supports ENCODING (the easier part). nvidia linux DECODING (the hard part) is still under development. there is no ETA, do not ask, it will be released when it is ready.

plex 4k/hevc decoding on linux/nvidia now available @ pms server beta @ [Plex Media Server - #286 by emilybersin](https://forums.plex.tv/t/plex-media-server/30447/286)

nvidia 4k transcoding generally needs a 10 series or equivilent gpu. generally minimal 4k working cards would be gtx 960 (gm206) or 1050 or p400 quadro. p2000 quadro is often recommended due to unlocked encoding streams (still the easier part)

-   for linux+nvidia, VIDEO RAM is very important. 4k transcodes require approx ~1.3 gigs of video ram PER 4k transcode. This means in most cases, VRAM will be the limit on the number of 4k transcodes. Non-4k transcodes will typically use less than 500 megs of video ram.
-   cards within the same generation have the same decode/encode chip, ie all pascal cards will have the same quality/speed for transcoding.

a great comparison page for plex GPU transcoding and additional details @ [nVidia Hardware Transcoding Calculator for Plex Estimates](https://www.elpamsoft.com/?p=Plex-Hardware-Transcoding)

there is a driver hack to unlocked some nvidia cards encoding, which may work, but that is obviously not something supported here or by plex. google is your friend.

the gtx 1030 does not have any encoder, so while it can decode 4k (the hard part), the cpu will be used to encode (the easier part).

amd gpu transcoding should work in windows, not sure about linux (I don’t know the details here, will update over time)

related plex support articles  
[https://support.plex.tv/articles/115002178853-using-hardware-accelerated-streaming/](https://support.plex.tv/articles/115002178853-using-hardware-accelerated-streaming/)

___

## [](https://forums.plex.tv/t/info-plex-4k-transcoding-and-you-aka-the-rules-of-4k/378203#some-questions-answers-solutions-4)some questions, answers, solutions

-   [Why does vlc/kodi/infuse/(any other common apps?) direct play my 4k content, while plex player doesn’t?](https://forums.plex.tv/t/info-plex-4k-transcoding-and-you-aka-the-rules-of-4k/378203#Q1)
-   [Why is my 4k smart tv app transcoding? its 4k it should be direct playing?!!?!? netflix/hulu/amazon/etc play in 4k with no problem?](https://forums.plex.tv/t/info-plex-4k-transcoding-and-you-aka-the-rules-of-4k/378203#Q2)
-   [Why doesn’t my 4k smart tv direct play hd audio?](https://forums.plex.tv/t/info-plex-4k-transcoding-and-you-aka-the-rules-of-4k/378203#Q3)
-   [Ok how do I get my HD audio along with 4k to direct play ?!?!?](https://forums.plex.tv/t/info-plex-4k-transcoding-and-you-aka-the-rules-of-4k/378203#Q4)
-   [how can I determine exactly why plex is transcoding?](https://forums.plex.tv/t/info-plex-4k-transcoding-and-you-aka-the-rules-of-4k/378203#Q5)

  
Q: Why does vlc/kodi/infuse/(any other common apps?) direct play my 4k content, while plex player doesn’t?

-   A: those applications are custom designed standalone applications which have their own built in codecs and capabilities and do not require a server, while plex clients are typically a lightweight app that depends more on the DEVICE to do the playback of directly compatible containers/codecs and make use of the SERVER to do the heavy lifting to convert (transcode) content which is not directly handled by the device/player.

___

  
Q: Why is my 4k smart tv app transcoding? its 4k it should be direct playing?!!?!? netflix/hulu/amazon/etc play in 4k with no problem?

-   A: smart tvs do not normally support the HD AUDIO that is included with 4k bluray rips/remuxes. when you are ripping your own 4k disks, you can see and choose which audio streams are included, make sure to include an dolby digital or dts 5.1 or stereo stream.  
    then when you are going to play a movie, make sure that 5.1 or stereo stream is selcted.  
    netflix etc does not use HD audio so it does not have this problem.  
    also, netflix etc have greater control over both their APP and the how their CONTENT is encoded, so they can match them up to get the best experience.  
    plex has to deal with content from all over the place, with unknown/inconsistent qualities and codec variations. Streaming 4k is also MUCH lower bitrate than 4k bluray remuxes.

___

  
Q: Why doesn’t my 4k smart tv direct play hd audio?

-   A: most smart tvs are made as cheaply as possible, have crappy speakers, and only include the bare minimum codecs and functionality required to get the job done.  
    so mostly only dolbydigital/dts 5.1 or stereo is directly compatible.  
    most smart tvs do allow for hdmi passthrough via something called ARC.  
    however ARC does not support the HD audio as explained previously, so again dd/dts 5.1 or stereo is generally the best that can come out of the tv.  
    some brand new tvs and receivers support a new version of HDMI which has hd audio support via E-ARC.  
    even then, e-arc support is still in its infancy.

___

  
Q: Ok how do I get my HD audio along with 4k to direct play ?!?!?

-   A: you must use a plex client that can directly handle the codecs you are using, including the HD audio. This will likely NOT be your smart TV, it will be a separate device. You must also have the HARDWARE (ie receiver) that can handle the hd audio, like an atmos/4k receiver.

I use an nvidia shield with no issues and I highly recommend them, but you still need an atmos/4k receiver to direct play 4k/hdr/hd-audio content.

nvidia shield + 4k/atmos receiver + 4k tv = the simplest full 4k solution (dolby vision support has been added to the plex android clients, not all clients support all the different dolby vision profiles).

dolby vision rips should be created with makemkv version 1.15.3 or newer to have the proper mkv container compatiblity see @ [http://www.makemkv.com/](http://www.makemkv.com/)

there are other possible solutions, but I don’t have any experience with them and cannot recommend them, perhaps others will list their recommendations.

___

  
Q: how can I determine exactly why plex is transcoding?

-   A: go to [Plex](https://app.plex.tv/desktop) > settings > console > filter > type “mde” without the quotes
-   play the video on the device in question
-   examine the log entries with the MDE: and TPU: lines, these should help explain why plex is transcoding.

in the logs, look for entries with  
`mde:` will tell WHY something is transcoded  
`tpu:` will tell you WHAT cpu/or gpu transcoder mode is used

you can see/filter the logs @ [https://app.plex.tv/desktop](https://app.plex.tv/desktop) > settings > console

or settings > troubleshooting > download logs

___

What about DOLBY VISION ?  
DV is a whole other can of worms. Again the 2019 shield pro is your best bet, but some DV compatible tvs can support DV playback with the plex smart tv app.

Not all TV’s support all the various DV profiles (of which there are several).

Instead of repeating existing good info/discussion, please see these links:

Dolby Vision primer @ [Demystifying Dolby Vision - Profile Levels, Dolby Vision levels, MEL & FEL - Home Theater Lobby - AV Discourse Community Forum (SG)](https://avdisco.com/t/demystifying-dolby-vision-profile-levels-dolby-vision-levels-mel-fel/95)

DV and plex discussion @

___

I hope this can be helpful.

feel free to post other questions, answers, solutions, corrections, or any other feedback.

this topic is a work in progress and with your help, I’ll attempt to keep updated and corrected as needed.

## References

- https://forums.plex.tv/t/info-plex-4k-transcoding-and-you-aka-the-rules-of-4k/378203

