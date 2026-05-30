"""법령 connector — 국가법령정보센터 (law.go.kr).

규정 판단의 1차 근거. SourceTier.LAW / SourceTier.NOTICE 를 반환.
"""
from data_layer.connectors.law.law_go_kr import LawGoKrConnector

__all__ = ["LawGoKrConnector"]
