import argparse
import sys
import traceback
from pathlib import Path


from src.config import Config
from src.logger import setup_logger
from src.pipeline import Pipeline



def parse_args():

    parser = argparse.ArgumentParser(

        description=
        "Generate subtitles using Qwen3-ASR"

    )


    parser.add_argument(

        "video",

        help=
        "Input video file path"

    )


    parser.add_argument(

        "--config",

        default=
        "config/config.yaml",

        help=
        "Config file path"

    )


    return parser.parse_args()





def main():

    #
    # 初始化日志
    #

    logger = setup_logger()



    try:


        #
        # 命令行参数
        #

        args = parse_args()



        video = Path(
            args.video
        )



        #
        # 检查视频
        #

        if not video.exists():

            logger.error(

                f"Video not found: {video}"

            )

            return 1



        if not video.is_file():

            logger.error(

                f"Not a file: {video}"

            )

            return 1



        logger.info(

            "=" * 60

        )


        logger.info(

            "video2srt started"

        )


        logger.info(

            f"Input: {video}"

        )



        #
        # 加载配置
        #

        config = Config(

            args.config

        )


        logger.info(

            "Config loaded"

        )



        #
        # 初始化 Pipeline
        #
        # 这里会加载:
        #
        # Qwen3-ASR
        #
        # ForcedAligner
        #

        pipeline = Pipeline(

            config

        )



        #
        # 执行
        #

     
        srt_file = pipeline.run(video)


        logger.info(
            f"Subtitle created: {srt_file}"
        )




        #
        # Step5:
        # 这里以后接 SRT Writer
        #

        logger.info(

            "SRT writer not implemented yet"

        )


        return 0



    except KeyboardInterrupt:


        logger.warning(

            "Interrupted by user"

        )


        return 130



    except Exception as e:


        logger.error(

            "Fatal error"

        )


        logger.error(

            str(e)

        )


        logger.error(

            traceback.format_exc()

        )


        return 1





if __name__ == "__main__":


    sys.exit(

        main()

    )