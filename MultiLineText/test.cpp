#include <iostream>

std::string addSoftReturnsToText(std::string &str, float multilineWidth)
{

	float textSize = 0;
	std::string tmpStr = "";
	std::string finalStr = "";
	int curChr = 0;
	while (curChr < str.size())
	{
		if (str[curChr] == '\n')
		{
			finalStr += tmpStr + "\n";
			tmpStr = "";
		}

		tmpStr += str[curChr];
		// textSize = ImGui::CalcTextSize(tmpStr.c_str()).x;
		textSize = 10;
		// 到达wrap宽度
		if (textSize > multilineWidth)
		{
			int lastSpace = tmpStr.size() - 1;
			// 从后往前找 第一个为 ' ' 空格的字符
			while (tmpStr[lastSpace] != ' ' && lastSpace > 0)
				lastSpace--;
			if (lastSpace == 0)
				lastSpace = tmpStr.size() - 2;
			finalStr += tmpStr.substr(0, lastSpace + 1) + "\r\n";
			if (lastSpace + 1 > tmpStr.size())
				tmpStr = "";
			else
				tmpStr = tmpStr.substr(lastSpace + 1);
		}
		curChr++;
	}
	if (tmpStr.size() > 0)
		finalStr += tmpStr;

	return finalStr;
};
int main()
{
	return 0;
}