FROM mcr.microsoft.com/dotnet/runtime:10.0

ADD --checksum=sha256:b16981befe5231d5ed153250de22d9382fb5bbb248d020c32654c4baa891b277 \
    https://github.com/studyzy/imewlconverter/releases/download/v3.6.0/imewlconverter_linux-x64.tar.gz \
    /tmp/imewlconverter.tar.gz

RUN mkdir -p /app \
 && tar -xzf /tmp/imewlconverter.tar.gz -C /app \
 && rm /tmp/imewlconverter.tar.gz \
 && chmod +x /app/ImeWlConverterCmd

WORKDIR /app

ENTRYPOINT ["/app/ImeWlConverterCmd"]
