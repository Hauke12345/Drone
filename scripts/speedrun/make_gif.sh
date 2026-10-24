# make.sh OUT SPEED FPS WIDTH LOSSY COLORS
IN=/home/claude/frame/speedrun/AeroFrame35_speedrun_fem_cfd.mp4; OUT=$1; SP=$2; FPS=$3; WD=$4; LOSSY=$5; NC=${6:-192}
F="setpts=PTS/$SP,fps=$FPS,scale=$WD:-2:flags=lanczos"
ffmpeg -y -loglevel error -i $IN -vf "$F,palettegen=max_colors=$NC:stats_mode=diff" pal_$OUT.png
ffmpeg -y -loglevel error -i $IN -i pal_$OUT.png -lavfi "$F[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" raw_$OUT.gif
gifsicle -O3 --lossy=$LOSSY --loopcount=forever raw_$OUT.gif -o $OUT.gif
echo "$OUT $(gifsicle --info $OUT.gif | head -1 | grep -o '[0-9]* images') $(du -k $OUT.gif | cut -f1) KB"
