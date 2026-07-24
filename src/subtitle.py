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
        seconds:
            float

        return:

            HH:MM:SS,mmm

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



    def write(
        self,
        align_result,
        output_file
    ):

        """
        写入 SRT

        align_result:
            ForcedAlignResult


        output_file:
            xxx.srt

        """


        output_file = Path(
            output_file
        )


        self.logger.info(
            f"Writing subtitle: {output_file}"
        )


        items = (
            align_result.items
        )


        lines = []


        index = 1


        for item in items:


            text = item.text.strip()


            if not text:

                continue



            start = self.format_time(

                item.start_time

            )


            end = self.format_time(

                item.end_time

            )


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