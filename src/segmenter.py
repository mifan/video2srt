import logging
import re



class SubtitleSegmenter:


    def __init__(
        self,
        max_chars_per_line=22,
        max_lines=2,
        max_duration=6.0,
        max_cps=15
    ):

        self.logger = logging.getLogger(
            "video2srt"
        )


        self.max_chars_per_line = (
            max_chars_per_line
        )

        self.max_lines = max_lines

        self.max_duration = (
            max_duration
        )

        self.max_cps = max_cps



    #
    # 判断中文
    #

    def is_chinese(
        self,
        ch
    ):

        return (
            '\u4e00'
            <= ch
            <=
            '\u9fff'
        )



    #
    # 计算字幕长度
    #

    def text_length(
        self,
        text
    ):

        length = 0


        for c in text:


            if self.is_chinese(c):

                length += 1


            elif c.isalpha():

                length += 0.5


            else:

                length += 0.5


        return length



    #
    # 是否应该切割
    #

    def should_split(
        self,
        text,
        duration
    ):


        #
        # 时间过长
        #

        if duration >= self.max_duration:

            return True



        #
        # CPS过高
        #

        if duration > 0:

            cps = (
                self.text_length(text)
                /
                duration
            )

            if cps > self.max_cps:

                return True



        #
        # 长度
        #

        if (
            self.text_length(text)
            >=
            self.max_chars_per_line * 2
        ):

            return True



        #
        # 标点
        #

        if text.endswith(

            (
                "。",
                "！",
                "？",
                ".",
                "!",
                "?",
                "；",
                ";"

            )

        ):

            return True



        return False




    #
    # 智能断行
    #

    def format_lines(
        self,
        text
    ):


        if (
            self.text_length(text)
            <=
            self.max_chars_per_line
        ):

            return text



        #
        # 找最佳切割点
        #

        middle = len(text)//2



        best = None


        for i in range(

            max(
                0,
                middle-10
            ),

            min(
                len(text),
                middle+10
            )

        ):


            if text[i] in [

                "，",
                "。",
                "！",
                "？",
                ",",
                ".",
                "!",
                "?"

            ]:

                best=i+1

                break



        if best:


            return (

                text[:best]

                +

                "\n"

                +

                text[best:]

            )



        #
        # 没找到标点
        #

        return (

            text[:middle]

            +

            "\n"

            +

            text[middle:]

        )



    #
    # 主入口
    #

    def segment(
        self,
        align_result
    ):


        items = (
            align_result.items
        )


        segments = []


        current = []

        start = None



        for item in items:


            if start is None:

                start = item.start_time



            current.append(item)



            text = "".join(

                x.text

                for x in current

            )



            duration = (

                item.end_time

                -

                start

            )



            if self.should_split(

                text,

                duration

            ):


                segments.append(

                    self.make_segment(
                        current,
                        start
                    )

                )


                current=[]

                start=None



        #
        # 尾部
        #

        if current:


            segments.append(

                self.make_segment(
                    current,
                    start
                )

            )



        return segments




    def make_segment(
        self,
        items,
        start
    ):


        text = "".join(

            x.text

            for x in items

        )


        return {

            "start":
                start,

            "end":
                items[-1].end_time,


            "text":
                self.format_lines(
                    text
                )

        }