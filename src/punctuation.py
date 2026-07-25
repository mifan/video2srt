import logging



class PunctuationRestorer:


    def __init__(self):

        self.logger = logging.getLogger(
            "video2srt"
        )



    def restore(
        self,
        text,
        original_text
    ):

        """
        根据ASR原始文本恢复标点

        text:
            ForcedAligner拼接文本

        original_text:
            ASR输出文本
        """


        if not text:

            return text


        if not original_text:

            return text



        #
        # 去除空格
        #

        clean_original = (
            original_text
            .replace(
                "\n",
                ""
            )
            .strip()
        )


        clean_text = (
            text
            .replace(
                "\n",
                ""
            )
            .strip()
        )



        result = ""


        index = 0



        for ch in clean_text:


            result += ch


            #
            # 在原始文本中寻找当前位置
            #

            pos = (
                clean_original.find(
                    ch,
                    index
                )
            )


            if pos == -1:

                continue



            index = pos + 1



            #
            # 查看后一个字符
            #

            if index < len(clean_original):


                next_char = (
                    clean_original[index]
                )


                if next_char in [

                    "，",
                    "。",
                    "！",
                    "？",
                    "；",
                    ",",
                    ".",
                    "!",
                    "?",
                    ";"

                ]:

                    result += next_char

                    index += 1



        return result