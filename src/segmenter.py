import logging



class SubtitleSegmenter:


    def __init__(
        self,
        max_chars=20,
        max_duration=5.0
    ):

        self.logger = logging.getLogger(
            "video2srt"
        )


        self.max_chars = max_chars

        self.max_duration = max_duration



    def segment(
        self,
        align_result
    ):


        items = align_result.items


        segments = []


        current_text = ""

        start_time = None

        end_time = None



        for item in items:


            if start_time is None:

                start_time = item.start_time



            current_text += item.text


            end_time = item.end_time



            duration = (
                end_time -
                start_time
            )



            #
            # 分割条件
            #

            if (

                len(current_text)
                >= self.max_chars

                or

                duration
                >= self.max_duration

                or

                item.text in [
                    "。",
                    "！",
                    "？",
                    ".",
                    "!",
                    "?"
                ]

            ):


                segments.append(

                    {

                        "start":
                            start_time,

                        "end":
                            end_time,

                        "text":
                            current_text

                    }

                )


                current_text = ""

                start_time = None



        #
        # 剩余文本
        #

        if current_text:


            segments.append(

                {

                    "start":
                        start_time,

                    "end":
                        end_time,

                    "text":
                        current_text

                }

            )


        return segments