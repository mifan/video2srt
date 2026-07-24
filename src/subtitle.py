import logging
from pathlib import Path



class SRTWriter:


    def __init__(self):

        self.logger = logging.getLogger(
            "video2srt"
        )



    def format_time(
        self,
        seconds
    ):
        """
        Convert seconds to SRT timestamp

        Example:

        1.234

        ->
        
        00:00:01,234

        """


        milliseconds = int(
            round(seconds * 1000)
        )


        hours = milliseconds // 3600000

        milliseconds %= 3600000


        minutes = milliseconds // 60000

        milliseconds %= 60000


        secs = milliseconds // 1000

        ms = milliseconds % 1000



        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{secs:02d},"
            f"{ms:03d}"
        )



    def clean_text(
        self,
        text
    ):

        """
        清理字幕文本
        """


        if text is None:

            return ""


        text = str(text)


        #
        # 去掉多余空格
        #

        text = (
            text
            .replace(
                "\n",
                " "
            )
            .strip()
        )


        return text



    def write(
        self,
        segments,
        output_file
    ):

        """
        Generate SRT file

        segments:

        [
            {
                start: float,
                end: float,
                text: str
            }
        ]

        """


        output_file = Path(
            output_file
        )


        self.logger.info(
            f"Writing SRT: {output_file}"
        )



        lines = []


        index = 1



        for seg in segments:


            text = self.clean_text(
                seg.get(
                    "text",
                    ""
                )
            )


            if not text:

                continue



            start = self.format_time(

                seg["start"]

            )


            end = self.format_time(

                seg["end"]

            )



            #
            # SRT block
            #

            lines.append(
                str(index)
            )


            lines.append(

                f"{start} --> {end}"

            )


            lines.append(
                text
            )


            lines.append(
                ""
            )


            index += 1



        output_file.write_text(

            "\n".join(lines),

            encoding="utf-8"

        )



        self.logger.info(

            f"SRT generated: {output_file}"

        )


        return output_file