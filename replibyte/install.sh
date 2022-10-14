# download latest replibyte archive for Linux
curl -s https://api.github.com/repos/Qovery/replibyte/releases/latest | \
jq -r '.assets[].browser_download_url' | \
grep -i 'linux-musl.tar.gz$' | wget -qi - && \

# unarchive
tar zxf *.tar.gz

# make replibyte executable
chmod +x replibyte

# make it accessible from everywhere
mv replibyte /usr/local/bin/