import logging


class SubtitleSegmenter:


    def __init__(
        self,
        max_chars=24,
        max_duration=6.0,
        max_cps=15
    ):

        self.logger = logging.getLogger(
            "video2srt"
        )


        # 单行最大长度
        self.max_chars = max_chars


        # 最大显示时间
        self.max_duration = max_duration


        # characters per second
        self.max_cps = max_cps



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



    def should_split(
        self,
        text,
        duration
    ):


        #
        # 遇到句号等强标点
        #

        if text.endswith(
            (
                "。",
                "！",
                "？",
                ".",
                "!",
                "?"
            )
        ):

            return True



        #
        # 时间过长
        #

        if duration >= self.max_duration:

            return True



        #
        # 单行长度
        #

        if (
            self.text_length(text)
            >= self.max_chars
        ):

            return True



        #
        # 阅读速度
        #

        if duration > 0:

            cps = (
                self.text_length(text)
                /
                duration
            )

            if cps > self.max_cps:

                return True



        return False




    def segment(
        self,
        align_result
    ):


        items = align_result.items


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
        # 最后一段
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
                text.strip()

        }