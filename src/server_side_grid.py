from pydantic import BaseModel, Field
from typing import Any, Generic, Literal, TypeVar

ModelT = TypeVar("ModelT", bound=BaseModel)


class ColumnVO(BaseModel):
    id: str
    displayName: str
    field: str | None = None
    aggFunc: str | None = None


FilterModel = dict[str, Any]


class JoinAdvancedFilterModel(BaseModel):
    filterType: Literal["join"] = "join"
    operator: Literal["AND", "OR"] = "AND"
    conditions: list["AdvancedFilterModel"]


TextAdvancedFilterModelType = Literal[
    "contains",
    "notContains",
    "equals",
    "notEqual",
    "startsWith",
    "endsWith",
    "blank",
    "notBlank",
]


class TextAdvancedFilterModel(BaseModel):
    colId: str
    filterType: Literal["text"] = "text"
    type: TextAdvancedFilterModelType
    filter: str | None = None


ScalarAdvancedFilterModelType = Literal[
    "equals",
    "notEqual",
    "lessThan",
    "lessThanOrEqual",
    "greaterThan",
    "greaterThanOrEqual",
    "blank",
    "notBlank",
]


class NumberAdvancedFilterModel(BaseModel):
    colId: str
    type: ScalarAdvancedFilterModelType
    filterType: Literal["number"] = "number"
    filter: int | None = None


class BooleanAdvancedFilterModel(BaseModel):
    colId: str
    type: Literal["true", "false"]
    filterType: Literal["boolean"] = "boolean"


class DateAdvancedFilterModel(BaseModel):
    colId: str
    type: ScalarAdvancedFilterModelType
    filterType: Literal["date"] = "date"
    filter: str | None = None


class DateStringAdvancedFilterModel(DateAdvancedFilterModel):
    filterType: Literal["dateString"] = "dateString"


class ObjectAdvancedFilterModel(BaseModel):
    colId: str
    type: TextAdvancedFilterModelType
    filterType: Literal["object"] = "object"
    filter: str | None = None


ColumnAdvancedFilterModel = (
    TextAdvancedFilterModel
    | NumberAdvancedFilterModel
    | BooleanAdvancedFilterModel
    | DateAdvancedFilterModel
    | DateStringAdvancedFilterModel
    | ObjectAdvancedFilterModel
)
AdvancedFilterModel = JoinAdvancedFilterModel | ColumnAdvancedFilterModel


class SortModelItem(BaseModel):
    colId: str
    sort: Literal["asc", "desc"]


class IServerSideGetRowsRequest(BaseModel):
    """https://www.ag-grid.com/react-data-grid/server-side-model-datasource/#registering-the-datasource"""

    startRow: int | None = None
    endRow: int | None = None
    rowGroupCols: list[ColumnVO] = Field(default_factory=list)
    valueCols: list[ColumnVO] = Field(default_factory=list)
    pivotCols: list[ColumnVO] = Field(default_factory=list)
    pivotMode: bool
    groupKeys: list[str] = Field(default_factory=list)
    filterModel: FilterModel | AdvancedFilterModel | None = None
    sortModel: list[SortModelItem] = Field(default_factory=list)


class LoadSuccessParams(BaseModel, Generic[ModelT]):
    rowData: list[ModelT]
    rowCount: int | None = None
    groupLevelInfo: Any | None = None
    pivotResultFields: list[str] | None = None
